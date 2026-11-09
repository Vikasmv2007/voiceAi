import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
DATABASE = os.path.join(BASE_DIR, "restaurant.db")
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
PHONE_DEV = os.getenv("PHONE_DEV") == "1"

# ---- Staff PIN ----
# Confirming orders (cash collected / UPI received) and editing the menu need this PIN,
# so a customer cannot confirm their own order by calling the API. Set it in .env.
STAFF_PIN = (os.getenv("STAFF_PIN") or "").strip()                              # 1 = skip signature check (local testing ONLY)
