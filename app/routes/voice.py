import re

from flask import Blueprint, request, jsonify, Response
from app.services import gnani_stt, gnani_tts, order_engine

bp = Blueprint("voice", __name__, url_prefix="/api")


@bp.route("/stt", methods=["POST"])
def stt():
    audio = request.files.get("audio")
    if not audio:
        return jsonify({"error": "No audio received"}), 400
    language = request.form.get("language", "en-IN")
    try:
        result = gnani_stt.transcribe(audio.read(), language)
    except gnani_stt.SttError as e:
        return jsonify({"error": str(e)}), 502
    return jsonify(result)


@bp.route("/turn", methods=["POST"])
def turn():
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    session_id = data.get("session_id") or ""
    if not text or not session_id:
        return jsonify({"error": "text and session_id are required"}), 400
    # Optional: who is ordering (browser id, for "same as last time") and a table number from a QR code.
    customer_id = str(data.get("customer_id") or "")[:64]
    if not re.fullmatch(r"[A-Za-z0-9_.:+-]+", customer_id):
        customer_id = None
    table = str(data.get("table") or "").strip()
    order_type = str(data.get("order_type") or "").strip().lower()
    if order_type == "takeaway":
        serving = {"type": "takeaway", "table": None}
    elif order_type == "dine-in":
        serving = {"type": "dine-in", "table": table if re.fullmatch(r"[1-9][0-9]?", table) else None}
    elif re.fullmatch(r"[1-9][0-9]?", table):
        serving = {"type": "dine-in", "table": table}
    else:
        serving = None
    customer_name = str(data.get("customer_name") or "").strip()[:50] or None
    customer_phone = str(data.get("customer_phone") or "").strip()[:15] or None
    payment_mode = str(data.get("payment_mode") or "").strip().lower() or None
    result = order_engine.handle_turn(
        session_id, text, data.get("language", "en-IN"),
        customer_id=customer_id, serving=serving,
        customer_name=customer_name, customer_phone=customer_phone,
        payment_mode=payment_mode
    )
    return jsonify(result)


@bp.route("/tts", methods=["POST"])
def tts():
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "text is required"}), 400
    try:
        audio, mime = gnani_tts.synthesize(text, data.get("language", "en-IN"))
    except gnani_tts.TtsError as e:
        return jsonify({"error": str(e)}), 502
    return Response(audio, mimetype=mime)
