"""Turns the customer's recorded speech into text using Gnani Prisma."""
import time

import requests

from app import config

STT_URL = "https://api.vachana.ai/stt/v3"
RETRY_STATUS = (429, 500, 502, 503, 504)


class SttError(Exception):
    pass


def transcribe(wav_bytes, language_code="en-IN"):
    if not config.GNANI_API_KEY:
        raise SttError("GNANI_API_KEY is missing in .env")
    last_error = "unknown error"
    for attempt in range(2):                      # one quick retry for busy/unstable moments
        try:
            r = requests.post(
                STT_URL,
                headers={"X-API-Key-ID": config.GNANI_API_KEY},
                files={"audio_file": ("speech.wav", wav_bytes, "audio/wav")},
                data={"language_code": language_code},
                timeout=60,
            )
        except requests.RequestException as e:
            last_error = f"Could not reach Gnani: {e}"
        else:
            if r.ok:
                try:
                    data = r.json()
                except ValueError:
                    raise SttError("Gnani sent an unreadable reply")
                return {"transcript": (data.get("transcript") or "").strip(), "raw": data}
            last_error = f"Gnani STT error {r.status_code}: {r.text[:300]}"
            if r.status_code not in RETRY_STATUS:
                break
        if attempt == 0:
            time.sleep(0.8)
    raise SttError(last_error)