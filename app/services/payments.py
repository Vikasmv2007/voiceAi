"""Razorpay: automatic UPI payment check (optional).

With RAZORPAY_KEY_ID + RAZORPAY_KEY_SECRET set:
  * web orders get a one-time UPI QR for the EXACT amount (instead of a plain upi:// link);
  * phone orders get a payment link by SMS (Razorpay sends it);
  * Razorpay calls /payments/razorpay/webhook when the money arrives, and the order is
    confirmed automatically (confirmed_by = "Razorpay").
Set the webhook in the Razorpay dashboard (events: qr_code.credited, payment_link.paid)
with the secret in RAZORPAY_WEBHOOK_SECRET. Without these keys, staff check UPI by hand.
"""
import hashlib
import hmac
import time

import requests

from app import config

API = "https://api.razorpay.com/v1"


class PaymentError(Exception):
    pass


def enabled():
    return bool(config.RAZORPAY_KEY_ID and config.RAZORPAY_KEY_SECRET)


def _post(path, body):
    try:
        r = requests.post(API + path, json=body, timeout=15,
                          auth=(config.RAZORPAY_KEY_ID, config.RAZORPAY_KEY_SECRET))
    except requests.RequestException as e:
        raise PaymentError(f"Could not reach Razorpay: {e}")
    if not r.ok:
        raise PaymentError(f"Razorpay error {r.status_code}: {r.text[:200]}")
    return r.json()


def create_qr(order_id, amount_rupees):
    """One-time UPI QR for exactly this amount. Returns {"id", "image_url"}."""
    data = _post("/payments/qr_codes", {
        "type": "upi_qr", "name": config.RESTAURANT_NAME[:40], "usage": "single_use",
        "fixed_amount": True, "payment_amount": int(amount_rupees) * 100,
        "description": f"Order {order_id}", "close_by": int(time.time()) + 30 * 60,
        "notes": {"order_id": str(order_id)},
    })
    return {"id": data["id"], "image_url": data.get("image_url")}


def create_payment_link(order_id, amount_rupees, phone=None, name=None):
    """Payment link sent by Razorpay over SMS. Returns {"id", "short_url"}."""
    body = {"amount": int(amount_rupees) * 100, "currency": "INR",
            "description": f"{config.RESTAURANT_NAME} order {order_id}"[:250],
            "reference_id": f"order-{order_id}-{int(time.time())}",
            "notes": {"order_id": str(order_id)}, "notify": {"sms": bool(phone), "email": False},
            "reminder_enable": False}
    if phone:
        body["customer"] = {"contact": phone, "name": (name or "Customer")[:50]}
    data = _post("/payment_links", body)
    return {"id": data["id"], "short_url": data.get("short_url")}


def verify_webhook(raw_body, signature):
    if not (config.RAZORPAY_WEBHOOK_SECRET and signature):
        return False
    expected = hmac.new(config.RAZORPAY_WEBHOOK_SECRET.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def parse_webhook(event):
    """-> (gateway object id, order id from notes, amount paid in paise, payment id) or None."""
    kind = event.get("event")
    payload = event.get("payload") or {}
    payment = ((payload.get("payment") or {}).get("entity")) or {}
    if kind == "qr_code.credited":
        obj = ((payload.get("qr_code") or {}).get("entity")) or {}
    elif kind == "payment_link.paid":
        obj = ((payload.get("payment_link") or {}).get("entity")) or {}
    else:
        return None
    notes = obj.get("notes") or payment.get("notes") or {}
    if isinstance(notes, list):        # Razorpay sends [] when there are no notes
        notes = {}
    return obj.get("id"), str(notes.get("order_id") or ""), int(payment.get("amount") or 0), payment.get("id")
