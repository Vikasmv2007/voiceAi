# Voice Order Agent

A voice ordering system for Indian restaurants. Customers order by speaking (or typing) in **English,
Hindi, Kannada, Tamil or Telugu**, on the web page, from a table QR code or over the phone. The kitchen
sees orders on a live dashboard. Speech uses Gnani (Prisma speech-to-text, Timbre voices).

**The golden rule:** a customer can only *submit* an order. It reaches the kitchen only after the payment
is verified: by the staff on the dashboard (cash collected / UPI seen in their UPI app), or automatically
by Razorpay when it is set up.

## Features

| For customers | For staff and owners |
|---|---|
| Voice or typed ordering in 5 languages, switches language automatically | Live kitchen board with sound and voice alerts |
| Menu with photos, tap a dish to add it | Confirm payment (cash or UPI), then Preparing → Ready → Delivered |
| Paid add-ons ("masala dosa with extra butter") | Kitchen tickets (KOT) for 80 mm thermal printers |
| "What is pongal?" answers from the menu description | GST tax invoice (CGST + SGST, GSTIN, invoice number) |
| Dine-in / takeaway / table number (QR code per table) | Full menu editor: add, edit, remove, photos, add-ons, stock counts |
| UPI QR or cash; automatic confirmation with Razorpay | Stock counts: dishes turn "sold out" by themselves |
| Waiting-time estimate, "order ready" alerts | Analytics: sales, busy hours, top dishes, repeat customers, ratings |
| WhatsApp / SMS updates (optional) | Staff logins (owner / staff) and a record of who confirmed each order |
| Cancel before payment is confirmed, rate the order after | Printable table QR codes |
| Phone ordering (Twilio), payment link by SMS | Rate limiting so nobody can spend your Gnani credits |

## Quick start (your computer)

```bash
python -m venv venv
venv\Scripts\activate            # Windows   (macOS/Linux: source venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env           # Windows   (macOS/Linux: cp .env.example .env)
```

Open `.env` and fill in at least `GNANI_API_KEY`, `RESTAURANT_NAME`, `UPI_ID`, `SECRET_KEY` and `STAFF_PIN`.

```bash
python -m app.seed_menu          # first time only: creates restaurant.db with a starter menu
python run.py
```

- Customer page: http://127.0.0.1:5000 (add `?table=5` for table 5)
- Kitchen dashboard: http://127.0.0.1:5000/dashboard
- Table QR codes: http://127.0.0.1:5000/dashboard/tables

Already have a `restaurant.db`? Don't seed again: new columns are added automatically at start-up and your
menu and orders are kept.

## Staff access

Pick one:
- **Staff logins (recommended):** run `python -m scripts.add_staff`. An *owner* can do everything; a
  *staff* login can handle orders but cannot change the menu. Each confirmation records who did it.
- **Shared PIN:** set `STAFF_PIN` in `.env`. The dashboard asks for it once.

If neither is set, staff actions are open to anyone and the app prints a warning.

## Optional services

| Setting in `.env` | What it adds |
|---|---|
| `GST_RATE`, `GSTIN` | GST on top of menu prices, split into CGST + SGST on the bill |
| `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET` | A one-time UPI QR for the exact amount, and automatic confirmation when the money arrives. Phone callers get a payment link by SMS. In the Razorpay dashboard, add the webhook `https://YOUR-SITE/payments/razorpay/webhook` with the events `qr_code.credited` and `payment_link.paid` |
| `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_TEMPLATE` | WhatsApp messages when an order is confirmed, ready or cancelled |
| `TWILIO_SMS_FROM` (+ Twilio SID/token) | The same messages by SMS (used when WhatsApp is not set up) |
| `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `PUBLIC_BASE_URL` | Phone ordering: point your Twilio number's voice webhook to `/phone/incoming` |
| `GNANI_VOICE_TA`, `GNANI_VOICE_TE` | Spoken replies in Tamil / Telugu (voice names from Gnani's catalog). Without them, Tamil and Telugu work as text, and the phone menu offers only the languages that have a voice |
| `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY` | An LLM helps with complicated sentences (any OpenAI-compatible API). The rules still handle prices and checkout |

## Going live (HTTPS)

Phone browsers only allow the microphone on **https** sites, so put the app on a server with HTTPS.

With Docker:
```bash
docker build -t voiceai .
docker run -d -p 8000:8000 --env-file .env -v voiceai-data:/data voiceai
```
Then put Caddy or nginx in front of it for HTTPS, and set `TRUST_PROXY=1`.

Without Docker: `gunicorn -w 2 --threads 4 -b 0.0.0.0:8000 run:app`.

Never set `FLASK_DEBUG=1` on a server.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest
```
GitHub Actions runs the same tests on every pull request.

Handy tools:
- `python -m scripts.chat_cli`: chat with the agent in the terminal (no voice credits used)
- `python -m scripts.seed_demo_orders`: fake orders for the analytics charts
- `python -m scripts.reset_orders`: delete all orders and keep the menu

## Project layout

```
app/
  services/order_engine.py   the conversation and checkout rules
  services/nlu.py            understanding what the customer said (rules, plus an optional LLM)
  services/texts.py          every sentence the agent says, in 5 languages
  services/kitchen.py        status changes, stock counts, waiting time, customer messages
  services/payments.py       Razorpay
  services/notify.py         WhatsApp / SMS
  routes/                    web pages and API
  templates/, static/        customer page, dashboard, bill, KOT, table QR codes
tests/                       pytest suite
```
