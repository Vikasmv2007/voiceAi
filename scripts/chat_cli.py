"""Chat with the order brain in the terminal (no microphone, no Gnani credits).

Run from the project root:   python -m scripts.chat_cli
Type  /hi  or  /kn  to switch language, /en to come back, Ctrl+C to quit.
"""
import uuid
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")   # Windows consoles cannot print ₹ / Hindi / Kannada otherwise

from app import create_app
from app.services import order_engine

app = create_app()
session = str(uuid.uuid4())
lang = "en-IN"
print("Type what the customer would say. (/hi = Hindi, /kn = Kannada, /en = English)")

with app.app_context():
    while True:
        try:
            text = input(f"[{lang}] You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            break
        if text in ("/hi", "/kn", "/en"):
            lang = {"/hi": "hi-IN", "/kn": "kn-IN", "/en": "en-IN"}[text]
            continue
        if not text:
            continue
        result = order_engine.handle_turn(session, text, lang)
        print("Agent:", result["reply"], f'   [understood by: {result["source"]}]')
        cart = result["cart"]
        if cart["items"]:
            print("   cart:", ", ".join(f'{i["quantity"]}x {i["name"]}' for i in cart["items"]), f'| total ₹{cart["total"]}')
        if result["submitted"]:
            print(f'   *** ORDER #{result["order_id"]} SUBMITTED ({result["status"]}) - the staff confirm it on the dashboard ***')
            session = str(uuid.uuid4())