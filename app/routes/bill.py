"""Printable bill for a confirmed order (/bill/<id>) and kitchen ticket (/kot/<id>)."""
from datetime import datetime, timedelta

from flask import Blueprint, abort, render_template

from app import config
from app.db import get_db
from app.services import pricing
from app.staff import page_guard

bp = Blueprint("bill", __name__)


def _ist(ts):
    """Times are stored in UTC; bills show Indian time."""
    return datetime.strptime(ts, "%Y-%m-%d %H:%M:%S") + timedelta(hours=5, minutes=30)


def _where(order):
    if order["order_type"] == "takeaway":
        return "Takeaway"
    if order["table_no"]:
        return "Dine-in · Table " + str(order["table_no"])
    return "Dine-in"


def _load(order_id):
    db = get_db()
    order = db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    # Not paid / not confirmed by the staff yet: no bill and no kitchen ticket.
    if not order or not order["confirmed_at"]:
        abort(404)
    lines = db.execute(
        """SELECT oi.quantity, oi.unit_price, oi.notes, oi.addons, m.name_en
           FROM order_items oi JOIN menu_items m ON m.id = oi.menu_item_id
           WHERE oi.order_id = ? ORDER BY oi.id""", (order_id,)).fetchall()
    return order, lines


@bp.route("/bill/<int:order_id>")
def bill(order_id):
    order, lines = _load(order_id)
    subtotal = order["subtotal"] or sum(l["quantity"] * l["unit_price"] for l in lines)
    tax = order["tax"] or 0
    cgst, sgst = pricing.split(tax)
    # Show the configured rate; for an old order billed at another rate, estimate it to 0.5%.
    half = config.GST_RATE / 2
    if subtotal and tax and abs(subtotal * config.GST_RATE / 100 - tax) > 1:
        half = round(tax * 100 / subtotal / 2 * 2) / 2
    money = {"subtotal": subtotal, "tax": tax, "cgst": cgst, "sgst": sgst, "half_rate": half,
             "total": subtotal + tax}
    return render_template(
        "bill.html", order=order, lines=lines, when=_ist(order["confirmed_at"]).strftime("%d %b %Y, %I:%M %p"),
        where=_where(order), name=config.RESTAURANT_NAME, address=config.RESTAURANT_ADDRESS,
        gstin=config.GSTIN, money=money, invoice_no=pricing.invoice_number(order["id"], order["created_at"]),
        cancelled=order["status"] == "CANCELLED")


@bp.route("/kot/<int:order_id>")
def kot(order_id):
    """Kitchen Order Ticket: big text, no prices, sized for 80 mm thermal printers."""
    guard = page_guard()
    if guard:
        return guard
    order, lines = _load(order_id)
    return render_template("kot.html", order=order, lines=lines, where=_where(order),
                           when=_ist(order["confirmed_at"]).strftime("%I:%M %p"))
