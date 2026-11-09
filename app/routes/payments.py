"""Razorpay webhook (payment arrived) and a small status check for the customer's page."""
import json

from flask import Blueprint, jsonify, request

from app.db import get_db
from app.services import kitchen, payments

bp = Blueprint("payments", __name__)


@bp.route("/payments/razorpay/webhook", methods=["POST"])
def razorpay_webhook():
    raw = request.get_data()
    if not payments.verify_webhook(raw, request.headers.get("X-Razorpay-Signature", "")):
        return jsonify({"error": "bad signature"}), 400
    try:
        info = payments.parse_webhook(json.loads(raw))
    except (ValueError, TypeError):
        return jsonify({"error": "bad body"}), 400
    if not info:
        return jsonify({"ignored": True})               # an event we do not use
    gateway_id, order_id, paise, payment_id = info
    db = get_db()
    row = None
    if order_id.isdigit():
        row = db.execute("SELECT * FROM orders WHERE id = ?", (int(order_id),)).fetchone()
    if row is None and gateway_id:
        row = db.execute("SELECT * FROM orders WHERE gateway_qr_id = ?", (gateway_id,)).fetchone()
    if row is None:
        return jsonify({"ignored": "unknown order"})
    if paise < row["total"] * 100:
        # Paid less than the bill (e.g. the cart changed): leave it for the staff to sort out.
        print(f"[payments] order {row['id']}: paid {paise / 100} but total is {row['total']}")
        return jsonify({"ignored": "amount mismatch"})
    if row["payment_ref"]:
        return jsonify({"ok": True, "duplicate": True})   # Razorpay retries: handle once
    db.execute("UPDATE orders SET payment_ref = ?, payment_mode = 'upi' WHERE id = ?", (payment_id or gateway_id, row["id"]))
    db.commit()
    if row["status"] == "AWAITING_UPI":
        kitchen.change_status(db, row["id"], "CONFIRMED", by="Razorpay")
    # Still DRAFT (customer has not reached the end of the chat): their next turn confirms it.
    return jsonify({"ok": True})


@bp.route("/api/orders/<int:order_id>/payment")
def payment_status(order_id):
    """The customer's page asks this while the Razorpay QR is on screen."""
    row = get_db().execute("SELECT status, payment_ref FROM orders WHERE id = ?", (order_id,)).fetchone()
    if not row:
        return jsonify({"error": "Order not found"}), 404
    return jsonify({"paid": bool(row["payment_ref"]), "status": row["status"]})
