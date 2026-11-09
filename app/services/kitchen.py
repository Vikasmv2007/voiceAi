"""Everything that happens when an order changes status, in ONE place:
confirmation (staff or Razorpay), stock counts, waiting-time estimate and customer messages."""
from app import config
from app.services import notify
from app.services.texts import LANGS, say

AWAITING_PAYMENT = ("AWAITING_CASH", "AWAITING_UPI")
LIVE = AWAITING_PAYMENT + ("CONFIRMED", "PREPARING", "READY")
NEXT = {"AWAITING_CASH": "CONFIRMED", "AWAITING_UPI": "CONFIRMED",
        "CONFIRMED": "PREPARING", "PREPARING": "READY", "READY": "DELIVERED"}


def eta_minutes(db, exclude_id=None):
    """Kitchen time for a new order: base prep time + a few minutes per order already ahead."""
    ahead = db.execute("SELECT COUNT(*) FROM orders WHERE status IN ('CONFIRMED', 'PREPARING') AND id != ?",
                       (exclude_id or 0,)).fetchone()[0]
    return config.PREP_MINUTES + config.MINUTES_PER_ORDER_AHEAD * ahead


def _use_stock(db, order_id):
    """Counted dishes go down when an order is confirmed; at 0 the dish shows as sold out."""
    for line in db.execute("SELECT menu_item_id, quantity FROM order_items WHERE order_id = ?", (order_id,)):
        db.execute("UPDATE menu_items SET stock = MAX(stock - ?, 0) WHERE id = ? AND stock IS NOT NULL",
                   (line["quantity"], line["menu_item_id"]))
    db.execute("UPDATE menu_items SET available = 0 WHERE stock IS NOT NULL AND stock <= 0")


def _return_stock(db, order_id):
    """A confirmed order was cancelled: put its counted dishes back."""
    for line in db.execute("SELECT menu_item_id, quantity FROM order_items WHERE order_id = ?", (order_id,)):
        db.execute("UPDATE menu_items SET stock = stock + ? WHERE id = ? AND stock IS NOT NULL",
                   (line["quantity"], line["menu_item_id"]))


def customer_message(order, status=None):
    """The sentence the customer gets for this status, in their language."""
    status = status or order["status"]
    lang = (order["language"] or "en").split("-")[0]
    lang = lang if lang in LANGS else "en"
    oid = order["id"]
    if status == "READY":
        if order["order_type"] == "takeaway":
            return say(lang, "ready_pickup", id=oid)
        if order["table_no"]:
            return say(lang, "ready_table", id=oid, table=order["table_no"])
        return say(lang, "order_ready", id=oid)
    key = {"AWAITING_CASH": "order_awaiting_cash", "AWAITING_UPI": "order_awaiting_upi",
           "CONFIRMED": "order_confirmed_kitchen", "PREPARING": "order_preparing",
           "CANCELLED": "order_cancelled_kitchen"}.get(status)
    if not key:
        return ""
    text = say(lang, key, id=oid)
    if status in ("CONFIRMED", "PREPARING") and order["eta_minutes"]:
        text += " " + say(lang, "eta", mins=order["eta_minutes"])
    return text


def _tell_customer(db, order_id):
    order = db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if order and order["customer_phone"] and order["status"] in ("CONFIRMED", "READY", "CANCELLED"):
        text = customer_message(order)
        if text:
            notify.send(order["customer_phone"], f"{config.RESTAURANT_NAME}: {text}")


def change_status(db, order_id, new_status, by=None):
    """Move an order one step. Returns (ok, error message)."""
    row = db.execute("SELECT status FROM orders WHERE id = ?", (order_id,)).fetchone()
    if not row:
        return False, "Order not found"
    current = row["status"]
    allowed = NEXT.get(current) == new_status or (new_status == "CANCELLED" and current in LIVE)
    if not allowed:
        return False, f"Cannot change {current} to {new_status}"
    if new_status == "CONFIRMED":
        # The staff (or Razorpay) have the money: confirmed from now; kitchen time starts.
        db.execute("UPDATE orders SET status = 'CONFIRMED', confirmed_at = CURRENT_TIMESTAMP,"
                   " confirmed_by = ?, eta_minutes = ? WHERE id = ?",
                   (by, eta_minutes(db, order_id), order_id))
        _use_stock(db, order_id)
    else:
        db.execute("UPDATE orders SET status = ? WHERE id = ?", (new_status, order_id))
        if new_status == "CANCELLED" and current in ("CONFIRMED", "PREPARING", "READY"):
            _return_stock(db, order_id)
    db.commit()
    _tell_customer(db, order_id)
    return True, None
