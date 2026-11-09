"""Telephone ordering, using Twilio-style webhooks.

How a call flows (the SAME order engine as the website, so the same rules apply):
  caller dials -> /phone/incoming  : "press 1 English, 2 Hindi, 3 Kannada"
              -> /phone/language   : greeting, then the line is recorded
              -> /phone/turn       : recording -> Gnani Prisma (speech to text) -> order engine
                                     -> Gnani Timbre (voice) -> played to the caller -> record again ...
  After the caller says yes to the read-back, the order is placed and the call ends.

Phone orders are always takeaway. The caller's number is the customer id (for "same as last time").
Payment: with Razorpay set up the caller gets a payment link by SMS and the order is confirmed when it
is paid; without it they pay at pickup and the staff confirm it then.
Switched off unless TWILIO_AUTH_TOKEN is set in .env (or PHONE_DEV=1 for local testing).
"""
import base64
import hashlib
import hmac
import re
import time
from xml.sax.saxutils import escape, quoteattr

import requests
from flask import Blueprint, Response, abort, request

from app import config
from app.services import gnani_stt, gnani_tts, order_engine, payments
from app.services.texts import say

bp = Blueprint("phone", __name__, url_prefix="/phone")

LANGS = {"1": "en-IN", "2": "hi-IN", "3": "kn-IN", "4": "ta-IN", "5": "te-IN"}
LANG_PROMPTS = [("en-IN", "For English, press 1."),
                ("hi-IN", "हिन्दी के लिए, 2 दबाएँ।"),
                ("kn-IN", "ಕನ್ನಡಕ್ಕಾಗಿ, 3 ಒತ್ತಿರಿ."),
                ("ta-IN", "தமிழுக்கு, 4 அழுத்தவும்."),
                ("te-IN", "తెలుగు కోసం, 5 నొక్కండి.")]
MAX_TURNS = 12              # hang up after this many back-and-forths
AUDIO = {}                  # token -> (bytes, mime): voice clips waiting for Twilio to fetch them


def _base():
    return config.PUBLIC_BASE_URL or request.url_root.rstrip("/")


def _guard():
    """Only Twilio may call these URLs (it signs every request with your auth token)."""
    if config.TWILIO_AUTH_TOKEN:
        url = _base() + request.full_path.rstrip("?")
        data = url + "".join(k + v for k, v in sorted(request.form.items(multi=True)))
        expected = base64.b64encode(
            hmac.new(config.TWILIO_AUTH_TOKEN.encode(), data.encode("utf-8"), hashlib.sha1).digest()).decode()
        if not hmac.compare_digest(expected, request.headers.get("X-Twilio-Signature", "")):
            abort(403)
    elif not config.PHONE_DEV:
        abort(503, "Phone ordering is switched off. Set TWILIO_AUTH_TOKEN in .env to switch it on.")


def _twiml(*verbs):
    return Response('<?xml version="1.0" encoding="UTF-8"?><Response>' + "".join(verbs) + "</Response>",
                    mimetype="text/xml")


def _play(text, language):
    """Voice clip made with Gnani Timbre, as a <Play> tag."""
    try:
        audio, mime = gnani_tts.synthesize(text, language)
    except gnani_tts.TtsError as e:
        print(f"[phone] TTS failed: {e}")
        return "<Say language=\"en-IN\">Sorry, we have a technical problem. Please call again.</Say><Hangup/>"
    token = hashlib.sha1(audio).hexdigest()[:32]
    AUDIO[token] = (audio, mime)
    while len(AUDIO) > 200:                     # keep memory small
        AUDIO.pop(next(iter(AUDIO)))
    return f"<Play>{escape(_base() + '/phone/audio/' + token)}</Play>"


def _record(language, turn):
    action = f"{_base()}/phone/turn?lang={language}&n={turn}"
    return (f'<Record action={quoteattr(action)} method="POST" maxLength="20" timeout="4" '
            f'playBeep="true" trim="trim-silence"/>')


def _fetch_recording(url):
    if not (url.startswith("https://api.twilio.com/") or config.PHONE_DEV):
        raise ValueError("recording URL is not from Twilio")
    auth = (config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN) if config.TWILIO_ACCOUNT_SID and config.TWILIO_AUTH_TOKEN else None
    for _ in range(4):                          # the file can take a moment to become ready
        r = requests.get(url + ".wav", auth=auth, timeout=10)
        if r.ok and r.content:
            return r.content
        time.sleep(0.7)
    raise RuntimeError("could not download the recording")


@bp.route("/incoming", methods=["POST"])
def incoming():
    _guard()
    # Only offer languages that have a Gnani voice (Tamil/Telugu need GNANI_VOICE_TA / _TE in .env).
    prompts = "".join(_play(text, lang) for lang, text in LANG_PROMPTS if lang in gnani_tts.VOICES)
    gather = (f'<Gather input="dtmf" numDigits="1" timeout="6" method="POST" '
              f'action={quoteattr(_base() + "/phone/language")}>{prompts}</Gather>')
    # No key pressed -> carry on in English.
    return _twiml(gather, f'<Redirect method="POST">{escape(_base() + "/phone/language?Digits=1")}</Redirect>')


@bp.route("/language", methods=["POST"])
def language():
    _guard()
    lang = LANGS.get(request.values.get("Digits", "1"), "en-IN")
    if lang not in gnani_tts.VOICES:
        lang = "en-IN"
    return _twiml(_play(say(lang.split("-")[0], "greet"), lang), _record(lang, 0))


@bp.route("/turn", methods=["POST"])
def turn():
    _guard()
    lang = request.args.get("lang", "en-IN")
    if lang not in LANGS.values() or lang not in gnani_tts.VOICES:
        lang = "en-IN"
    code = lang.split("-")[0]
    try:
        n = int(request.args.get("n", "0"))
    except ValueError:
        n = 0
    call_sid = (request.form.get("CallSid") or "")[:64]
    if not call_sid:
        abort(400)
    caller = (request.form.get("From") or "")[:30]
    if n >= MAX_TURNS:
        return _twiml(_play(say(code, "bye"), lang), "<Hangup/>")

    text = ""
    url = request.form.get("RecordingUrl") or ""
    try:
        seconds = int(request.form.get("RecordingDuration") or 0)
    except ValueError:
        seconds = 0
    if url and seconds > 0:
        try:
            text = (gnani_stt.transcribe(_fetch_recording(url), lang).get("transcript") or "").strip()
        except Exception as e:                  # a bad line should never crash the call
            print(f"[phone] could not understand the recording: {type(e).__name__}: {str(e)[:120]}")

    if not text:
        return _twiml(_play(say(code, "unknown"), lang), _record(lang, n + 1))

    result = order_engine.handle_turn(
        "call:" + call_sid, text, lang, customer_id=("tel:" + caller) if caller else None,
        channel="phone", serving={"type": "takeaway", "table": None},
        # A caller cannot scan a QR: with Razorpay they get a payment link by SMS, otherwise they pay at pickup.
        payment_mode="upi" if payments.enabled() else "cash")
    if result.get("language") in gnani_tts.VOICES:
        lang = result["language"]
    if result["submitted"]:
        return _twiml(_play(result["reply"], lang), _play(say(code, "bye"), lang), "<Hangup/>")
    return _twiml(_play(result["reply"], lang), _record(lang, n + 1))


@bp.route("/audio/<token>")
def audio(token):
    if not re.fullmatch(r"[0-9a-f]{32}", token) or token not in AUDIO:
        abort(404)
    data, mime = AUDIO[token]
    return Response(data, mimetype=mime)
