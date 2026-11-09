"""Printable bill for a confirmed order:  /bill/<order id>"""
from datetime import datetime, timedelta

from flask import Blueprint, abort, render_template

from app import config
from app.db import get_db

bp = Blueprint("bill", __name__)


@bp.route("/bill/<int:order_id>")
def bill(order_id):
    db = get_db()
    order = db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    # Drafts (not yet confirmed by the customer) never get a bill.
    if not order or not order["confirmed_at"]:
        abort(404)
    lines = db.execute(
        """SELECT oi.quantity, oi.unit_price, oi.notes, m.name_en
           FROM order_items oi JOIN menu_items m ON m.id = oi.menu_item_id
           WHERE oi.order_id = ? ORDER BY oi.id""", (order_id,)).fetchall()
    # Times are stored in UTC; the bill shows Indian time.
    when = datetime.strptime(order["confirmed_at"], "%Y-%m-%d %H:%M:%S") + timedelta(hours=5, minutes=30)
    if order["order_type"] == "takeaway":
        where = "Takeaway"
    elif order["table_no"]:
        where = "Dine-in · Table " + str(order["table_no"])
    else:
        where = "Dine-in"
    return render_template(
        "bill.html", order=order, lines=lines, when=when.strftime("%d %b %Y, %I:%M %p"), where=where,
        name=config.RESTAURANT_NAME, address=config.RESTAURANT_ADDRESS,
        cancelled=order["status"] == "CANCELLED")
