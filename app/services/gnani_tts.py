"""Turns the agent's reply text into speech using Gnani Timbre v2.5."""
import hashlib
import os
import re
import time

import requests

from app import config

TTS_URL = "https://api.vachana.ai/api/v1/tts/inference"
MODEL = "timbre-v2.5"
# One voice per language (from Gnani's voice catalog for Timbre v2.5).
VOICES = {"en-IN": "Kaveri", "hi-IN": "Nalini", "kn-IN": "Saanvi"}
# Tamil / Telugu voice names come from .env (GNANI_VOICE_TA / GNANI_VOICE_TE): copy them from
# Gnani's voice catalog. Until they are set, replies in those languages are shown as text only.
if config.GNANI_VOICE_TA:
    VOICES["ta-IN"] = config.GNANI_VOICE_TA
if config.GNANI_VOICE_TE:
    VOICES["te-IN"] = config.GNANI_VOICE_TE
# How to say the rupee sign out loud.
RUPEES = {"en-IN": "rupees", "hi-IN": "रुपये", "kn-IN": "ರೂಪಾಯಿ", "ta-IN": "ரூபாய்", "te-IN": "రూపాయలు"}
# On Vercel only /tmp is writable; the project folder itself is read-only.
CACHE_DIR = os.getenv("TTS_CACHE_DIR") or (
    "/tmp/tts_cache" if os.getenv("VERCEL") else os.path.join(config.BASE_DIR, "tts_cache"))
MAX_CHARS = 500
RETRY_STATUS = (429, 500, 502, 503, 504)


class TtsError(Exception):
    pass


def speakable(text, language):
    """'₹160' is written for the eyes; the voice should say '160 rupees'."""
    word = RUPEES.get(language, "rupees")
    return re.sub(r"₹\s?(\d+)", lambda m: f"{m.group(1)} {word}", text)


# Try small MP3 first; if Gnani rejects it, fall back to WAV.
FORMATS = [
    ("mp3", "audio/mpeg", {"sample_rate": 24000, "container": "mp3", "bitrate": "64k"}),
    ("wav", "audio/wav", {"sample_rate": 24000, "num_channels": 1, "sample_width": 2,
                          "encoding": "linear_pcm", "container": "wav"}),
]


def synthesize(text, language="en-IN"):
    """Return (audio_bytes, mime_type). Repeated sentences come from a local
    cache, so they cost no Gnani credits."""
    if not config.GNANI_API_KEY:
        raise TtsError("GNANI_API_KEY is not set (.env locally, Environment Variables on Vercel)")
    if language not in VOICES:
        if language in ("ta-IN", "te-IN"):
            raise TtsError(f"No Gnani voice set for {language}: add GNANI_VOICE_{language[:2].upper()} to .env")
        language = "en-IN"
    spoken = speakable(text, language)[:MAX_CHARS]
    voice = VOICES[language]

    key = hashlib.sha1(f"{MODEL}|{voice}|{language}|{spoken}".encode("utf-8")).hexdigest()
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
    except OSError:
        pass                                   # no cache on a read-only disk: just call Gnani
    for ext, mime, _ in FORMATS:
        path = os.path.join(CACHE_DIR, f"{key}.{ext}")
        try:
            if os.path.exists(path):
                with open(path, "rb") as f:
                    return f.read(), mime
        except OSError:
            pass

    last_error, last_status = "unknown error", None
    for ext, mime, audio_config in FORMATS:
        for attempt in range(2):                  # one quick retry for busy/unstable moments
            try:
                r = requests.post(
                    TTS_URL,
                    headers={"Content-Type": "application/json", "X-API-Key-ID": config.GNANI_API_KEY},
                    json={"text": spoken, "voice": voice, "model": MODEL, "language": language,
                          "speed": 1.0, "audio_config": audio_config},
                    timeout=30,
                )
            except requests.RequestException as e:
                last_error, last_status = f"Could not reach Gnani: {e}", None
                if attempt == 0:
                    time.sleep(0.8)
                    continue
                break
            if r.ok and r.content:
                try:
                    with open(os.path.join(CACHE_DIR, f"{key}.{ext}"), "wb") as f:
                        f.write(r.content)
                except OSError:
                    pass                         # audio still works without the cache
                return r.content, mime
            last_error, last_status = f"Gnani TTS error {r.status_code}: {r.text[:200]}", r.status_code
            if r.status_code in RETRY_STATUS and attempt == 0:
                time.sleep(0.8)
                continue
            break
        if last_status not in (400, 422):         # only a format problem is worth trying the other format
            break
    raise TtsError(last_error)