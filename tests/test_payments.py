"""Razorpay: automatic UPI confirmation through the signed webhook, and phone payment links."""
import hashlib
import hmac
import json

import pytest

from app import config
from app.services import payments
from tests.conftest import CHECKOUT, order_row


@pytest.fixture
def razorpay(monkeypatch):
    monkeypatch.setattr(config, "RAZORPAY_KEY_ID", "rzp_test_x")
    monkeypatch.setattr(config, "RAZORPAY_KEY_SECRET", "s")
    monkeypatch.setattr(config, "RAZORPAY_WEBHOOK_SECRET", "whsec")
    made = []

    def fake_qr(order_id, amount):
        made.append(("qr", order_id, amount))
        return {"id": f"qr_{order_id}_{amount}", "image_url": "https://rzp.io/qr.png"}

    def fake_link(order_id, amount, phone=None, name=None):
        made.append(("link", order_id, amount, phone))
        return {"id": f"plink_{order_id}", "short_url": "https://rzp.io/l/x"}
    monkeypatch.setattr(payments, "create_qr", fake_qr)
    monkeypatch.setattr(payments, "create_payment_link", fake_link)
    return made


def webhook(client, event, qr_id, order_id, paise, secret="whsec"):
    kind = "qr_code" if event == "qr_code.credited" else "payment_link"
    body = json.dumps({"event": event, "payload": {
        kind: {"entity": {"id": qr_id, "notes": {"order_id": str(order_id)}}},
        "payment": {"entity": {"id": "pay_123", "amount": paise}}}}).encode()
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return client.post("/payments/razorpay/webhook", data=body,
                       headers={"X-Razorpay-Signature": sig, "Content-Type": "application/json"})


def test_customer_saying_paid_is_not_enough(client, chat, razorpay):
    r = chat(CHECKOUT + ["upi", "I have paid", "confirm"])
    qr = r[7]
    assert qr["awaiting"] == "upi_confirm" and qr["upi"]["gateway"] and qr["upi"]["image_url"]
    assert not r[8]["submitted"] and not r[9]["submitted"]           # still waiting for Razorpay
    assert "not received" in r[8]["reply"]


def test_webhook_then_customer_turn_confirms(client, chat, razorpay):
    import uuid
    s = str(uuid.uuid4())
    r = chat(CHECKOUT + ["upi"], session=s)
    oid, total = r[-1]["order_id"], r[-1]["cart"]["total"]
    assert client.get(f"/api/orders/{oid}/payment").json["paid"] is False
    assert webhook(client, "qr_code.credited", f"qr_{oid}_{total}", oid, total * 100, secret="bad").status_code == 400
    assert webhook(client, "qr_code.credited", f"qr_{oid}_{total}", oid, total * 100).status_code == 200
    assert client.get(f"/api/orders/{oid}/payment").json["paid"] is True
    done = chat(["paid"], session=s)[0]                               # the page sends this automatically
    assert done["submitted"] and done["confirmed"] and done["status"] == "CONFIRMED"
    row = order_row(oid)
    assert row["confirmed_by"] == "Razorpay" and row["payment_ref"] == "pay_123"


def test_short_payment_is_not_accepted(client, chat, razorpay):
    r = chat(CHECKOUT + ["upi"])
    oid, total = r[-1]["order_id"], r[-1]["cart"]["total"]
    assert webhook(client, "qr_code.credited", "qr", oid, (total - 1) * 100).json["ignored"] == "amount mismatch"
    assert order_row(oid)["payment_ref"] is None


def test_cart_change_makes_a_new_qr(chat, razorpay):
    chat(CHECKOUT + ["upi", "also one coffee", "yes", "upi"])
    amounts = [m[2] for m in razorpay if m[0] == "qr"]
    assert amounts == [20, 40]


def test_phone_order_gets_payment_link_and_webhook_confirms(app, client, razorpay):
    from app.services import order_engine
    turns = ["I am Ravi", "one idli", "no", "that's all", "yes"]
    for t in turns:
        r = order_engine.handle_turn("call:CA1", t, "en-IN", customer_id="tel:+919876543210", channel="phone",
                                     serving={"type": "takeaway", "table": None}, customer_phone="9876543210",
                                     payment_mode="upi")
    assert r["submitted"] and r["status"] == "AWAITING_UPI" and "payment link" in r["reply"]
    assert razorpay[-1][0] == "link" and razorpay[-1][3] == "9876543210"
    oid = r["order_id"]
    assert webhook(client, "payment_link.paid", f"plink_{oid}", oid, r["cart"]["total"] * 100).status_code == 200
    assert order_row(oid)["status"] == "CONFIRMED"


def test_gateway_failure_falls_back_to_cash(chat, razorpay, monkeypatch):
    def broken(*a, **k):
        raise payments.PaymentError("down")
    monkeypatch.setattr(payments, "create_qr", broken)
    r = chat(CHECKOUT + ["upi"])
    assert r[-1]["submitted"] and r[-1]["status"] == "AWAITING_CASH"
