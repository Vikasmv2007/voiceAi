"""All settings, read from the .env file (see .env.example for every option)."""
import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
# On Vercel only /tmp can be written to (and it is erased between requests: see README "Going live").
DATABASE = os.getenv("DATABASE_PATH") or (
    "/tmp/restaurant.db" if os.getenv("VERCEL") else os.path.join(BASE_DIR, "restaurant.db"))
GNANI_API_KEY = os.getenv("GNANI_API_KEY")

# Optional LLM: any OpenAI-compatible chat API. Leave LLM_BASE_URL empty to run on rules only.
LLM_BASE_URL = (os.getenv("LLM_BASE_URL") or "").rstrip("/")
LLM_API_KEY = os.getenv("LLM_API_KEY") or ""
LLM_MODEL = os.getenv("LLM_MODEL") or ""
LLM_MODE = (os.getenv("LLM_MODE") or "fallback").strip().lower()   # off | fallback | always
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT") or 8)
LLM_EXTRA = os.getenv("LLM_EXTRA") or ""     # optional JSON added to every request

# ---- Printed bill ----
RESTAURANT_NAME = os.getenv("RESTAURANT_NAME") or "My Restaurant"
RESTAURANT_ADDRESS = os.getenv("RESTAURANT_ADDRESS") or ""

# ---- Payment / UPI QR ----
UPI_ID = os.getenv("UPI_ID") or "restaurant@upi"
UPI_PAYEE_NAME = os.getenv("UPI_PAYEE_NAME") or RESTAURANT_NAME

# ---- Telephone ordering (Twilio-style webhooks). Leave empty to keep it switched off. ----
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID") or ""
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN") or ""
PUBLIC_BASE_URL = (os.getenv("PUBLIC_BASE_URL") or "").rstrip("/")      # e.g. https://abc123.ngrok-free.app
PHONE_DEV = os.getenv("PHONE_DEV") == "1"                              # 1 = skip signature check (local testing ONLY)

# ---- Staff PIN ----
# Confirming orders (cash collected / UPI received) and editing the menu need this PIN,
# so a customer cannot confirm their own order by calling the API. Set it in .env.
STAFF_PIN = (os.getenv("STAFF_PIN") or "").strip()


def _int(name, default):
    try:
        return int(os.getenv(name) or default)
    except ValueError:
        return default


def _float(name, default):
    try:
        return float(os.getenv(name) or default)
    except ValueError:
        return default


# ---- Web server ----
SECRET_KEY = os.getenv("SECRET_KEY") or ""            # signs staff login cookies; set a long random value
DEBUG = os.getenv("FLASK_DEBUG") == "1"               # NEVER 1 on a public server
TRUST_PROXY = os.getenv("TRUST_PROXY") == "1"         # 1 when running behind nginx / Caddy / Render

# ---- GST on the bill ----
GST_RATE = _float("GST_RATE", 0)                      # e.g. 5 for 5% (2.5% CGST + 2.5% SGST). 0 = no GST lines
GSTIN = os.getenv("GSTIN") or ""

# ---- Kitchen ----
PREP_MINUTES = _int("PREP_MINUTES", 10)               # time for one order when the kitchen is free
MINUTES_PER_ORDER_AHEAD = _int("MINUTES_PER_ORDER_AHEAD", 3)

# ---- Abuse protection (per visitor IP, per minute) ----
RATE_LIMIT_TURN = _int("RATE_LIMIT_TURN", 40)
RATE_LIMIT_VOICE = _int("RATE_LIMIT_VOICE", 20)       # /api/stt and /api/tts cost Gnani credits
MAX_TEXT_CHARS = _int("MAX_TEXT_CHARS", 300)

# ---- Razorpay: automatic UPI payment check (leave empty to keep the manual staff check) ----
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID") or ""
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET") or ""
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET") or ""

# ---- Customer messages: WhatsApp Cloud API and/or Twilio SMS (leave empty = off) ----
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN") or ""
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID") or ""
WHATSAPP_TEMPLATE = os.getenv("WHATSAPP_TEMPLATE") or ""        # approved template with ONE body variable {{1}}
WHATSAPP_TEMPLATE_LANG = os.getenv("WHATSAPP_TEMPLATE_LANG") or "en"
TWILIO_SMS_FROM = os.getenv("TWILIO_SMS_FROM") or ""            # your Twilio number, e.g. +1415...
COUNTRY_CODE = os.getenv("COUNTRY_CODE") or "91"

# ---- Voices for the newer languages (Gnani Timbre voice names from your Gnani console) ----
GNANI_VOICE_TA = os.getenv("GNANI_VOICE_TA") or ""
GNANI_VOICE_TE = os.getenv("GNANI_VOICE_TE") or ""
