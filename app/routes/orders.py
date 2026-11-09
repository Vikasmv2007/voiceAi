"""Kitchen dashboard API: live orders, history, status changes, daily stats."""
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request

from app.db import get_db
from app.ratelimit import limit
from app.services import kitchen
from app.services.kitchen import AWAITING_PAYMENT, LIVE
from app.staff import staff_name, staff_only

bp = Blueprint("orders", __name__, url_prefix="/api")

# "Today" means today in India (UTC+5:30), not in UTC.
TODAY_IST = "date(o.confirmed_at, '+330 minutes') = date('now', '+330 minutes')"
COUNTED = "o.confirmed_at IS NOT NULL AND o.status != 'CANCELLED'"


def _iso(ts):
    """SQLite stores UTC as 'YYYY-MM-DD HH:MM:SS'; the browser converts it to local time."""
    return ts.replace(" ", "T") + "Z" if ts else None


def _load_orders(db, where, args, newest_first=False, limit=100):
    direction = "DESC" if newest_first else "ASC"
    rows = db.execute(
        f"SELECT * FROM orders WHERE {where} ORDER BY confirmed_at {direction}, id {direction} LIMIT ?",
        (*args, limit)).fetchall()
    if not rows:
        return []
    ids = [r["id"] for r in rows]
    marks = ",".join("?" * len(ids))
    items = db.execute(
        f"""SELECT oi.order_id, oi.quantity, oi.notes, oi.addons, m.name_en
            FROM order_items oi JOIN menu_items m ON m.id = oi.menu_item_id
            WHERE oi.order_id IN ({marks}) ORDER BY oi.id""", ids).fetchall()
    by_order = {}
    for it in items:
        by_order.setdefault(it["order_id"], []).append(
            {"name": it["name_en"], "quantity": it["quantity"], "notes": it["notes"], "addons": it["addons"]})
    return [{
        "id": r["id"],
        "status": r["status"],
        "language": r["language"],
        "total": r["total"],
        "order_type": r["order_type"],
        "table_no": r["table_no"],
        "channel": r["channel"],
        "customer_name": r["customer_name"] if "customer_name" in r.keys() else None,
        "customer_phone": r["customer_phone"] if "customer_phone" in r.keys() else None,
        "payment_mode": r["payment_mode"] if "payment_mode" in r.keys() else None,
        "confirmed_at": _iso(r["confirmed_at"]),
        "created_at": _iso(r["created_at"]),
        "confirmed_by": r["confirmed_by"],
        "eta_minutes": r["eta_minutes"],
        "subtotal": r["subtotal"],
        "tax": r["tax"],
        "items": by_order.get(r["id"], []),
    } for r in rows]


@bp.route("/orders/live")
def live_orders():
    marks = ",".join("?" * len(LIVE))
    return jsonify(_load_orders(get_db(), f"status IN ({marks})", LIVE))


@bp.route("/orders/history")
def order_history():
    limit = min(request.args.get("limit", 50, type=int), 200)
    # Customer-cancelled drafts never had confirmed_at, so they stay out of history.
    where = "confirmed_at IS NOT NULL AND status IN ('DELIVERED', 'CANCELLED')"
    return jsonify(_load_orders(get_db(), where, (), newest_first=True, limit=limit))


@bp.route("/orders/<int:order_id>/status", methods=["POST"])
@staff_only
def change_status(order_id):
    new_status = (request.get_json(silent=True) or {}).get("status", "")
    ok, error = kitchen.change_status(get_db(), order_id, new_status, by=staff_name() or "staff")
    if not ok:
        return jsonify({"error": error}), 404 if error == "Order not found" else 400
    return jsonify({"id": order_id, "status": new_status})


def _own_order(order_id):
    """The customer's own order: the browser must send the session id that placed it."""
    data = request.get_json(silent=True) or {}
    session_id = str(data.get("session_id") or "")
    row = get_db().execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if not row or not session_id or row["session_id"] != session_id:
        return None, data
    return row, data


@bp.route("/orders/<int:order_id>/customer-cancel", methods=["POST"])
@limit("customer", "RATE_LIMIT_TURN")
def customer_cancel(order_id):
    """A customer may cancel only while the staff have not confirmed the payment yet."""
    row, _ = _own_order(order_id)
    if not row:
        return jsonify({"error": "Order not found"}), 404
    if row["status"] not in AWAITING_PAYMENT:
        return jsonify({"error": "This order is already confirmed. Please ask the staff."}), 400
    if row["payment_ref"]:
        return jsonify({"error": "You have already paid online. Please ask the staff for a refund."}), 400
    db = get_db()
    db.execute("UPDATE orders SET status = 'CANCELLED' WHERE id = ?", (order_id,))
    db.commit()
    return jsonify({"id": order_id, "status": "CANCELLED"})


@bp.route("/orders/<int:order_id>/feedback", methods=["POST"])
@limit("customer", "RATE_LIMIT_TURN")
def feedback(order_id):
    """1-5 stars (and a short comment) after the order was delivered. One per order."""
    row, data = _own_order(order_id)
    if not row:
        return jsonify({"error": "Order not found"}), 404
    if row["status"] not in ("READY", "DELIVERED"):
        return jsonify({"error": "You can rate the order after you receive it."}), 400
    try:
        rating = int(data.get("rating"))
    except (TypeError, ValueError):
        rating = 0
    if not 1 <= rating <= 5:
        return jsonify({"error": "Rating must be 1 to 5"}), 400
    comment = str(data.get("comment") or "").strip()[:300]
    db = get_db()
    db.execute("INSERT OR REPLACE INTO feedback (order_id, rating, comment) VALUES (?, ?, ?)",
               (order_id, rating, comment))
    db.commit()
    return jsonify({"ok": True})


@bp.route("/feedback")
@staff_only
def feedback_list():
    rows = get_db().execute(
        "SELECT f.order_id, f.rating, f.comment, f.created_at, o.customer_name FROM feedback f"
        " JOIN orders o ON o.id = f.order_id ORDER BY f.created_at DESC LIMIT 50").fetchall()
    return jsonify([{**dict(r), "created_at": _iso(r["created_at"])} for r in rows])


@bp.route("/stats")
def stats():
    db = get_db()
    today = db.execute(
        f"SELECT COUNT(*) AS orders, COALESCE(SUM(o.total), 0) AS revenue FROM orders o "
        f"WHERE {COUNTED} AND {TODAY_IST}").fetchone()
    top_sql = (
        "SELECT m.name_en AS name, SUM(oi.quantity) AS quantity FROM order_items oi "
        "JOIN orders o ON o.id = oi.order_id JOIN menu_items m ON m.id = oi.menu_item_id "
        "WHERE {cond} GROUP BY m.id ORDER BY quantity DESC, m.name_en LIMIT 5")
    languages = db.execute(
        f"SELECT o.language AS language, COUNT(*) AS orders FROM orders o "
        f"WHERE {COUNTED} AND {TODAY_IST} GROUP BY o.language ORDER BY orders DESC").fetchall()
    n = today["orders"]
    return jsonify({
        "orders_today": n,
        "revenue_today": today["revenue"],
        "average_order": round(today["revenue"] / n) if n else 0,
        "top_today": [dict(r) for r in db.execute(top_sql.format(cond=f"{COUNTED} AND {TODAY_IST}"))],
        "top_all_time": [dict(r) for r in db.execute(top_sql.format(cond=COUNTED))],
        "languages": [dict(r) for r in languages],
    })


@bp.route("/analytics")
def analytics():
    """Bigger numbers for the owner: last 7 days, busy hours, weekly favourites, order types, repeat customers."""
    db = get_db()
    ist_day = "date(o.confirmed_at, '+330 minutes')"
    week = f"{COUNTED} AND {ist_day} >= date('now', '+330 minutes', '-6 days')"

    by_day = {r["day"]: r for r in db.execute(
        f"SELECT {ist_day} AS day, COUNT(*) AS orders, COALESCE(SUM(o.total), 0) AS revenue "
        f"FROM orders o WHERE {week} GROUP BY day")}
    today = (datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)).date()
    days = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        row = by_day.get(d.isoformat())
        days.append({"day": d.strftime("%a %d %b"), "orders": row["orders"] if row else 0,
                     "revenue": row["revenue"] if row else 0})

    hours = {int(r["hour"]): r["orders"] for r in db.execute(
        f"SELECT strftime('%H', o.confirmed_at, '+330 minutes') AS hour, COUNT(*) AS orders "
        f"FROM orders o WHERE {COUNTED} AND {ist_day} >= date('now', '+330 minutes', '-29 days') GROUP BY hour")}
    busy = [{"hour": h, "orders": n} for h, n in sorted(hours.items())]

    top_week = [dict(r) for r in db.execute(
        f"SELECT m.name_en AS name, SUM(oi.quantity) AS quantity FROM order_items oi "
        f"JOIN orders o ON o.id = oi.order_id JOIN menu_items m ON m.id = oi.menu_item_id "
        f"WHERE {week} GROUP BY m.id ORDER BY quantity DESC, m.name_en LIMIT 5")]

    types = [dict(r) for r in db.execute(
        f"SELECT CASE WHEN o.channel = 'phone' THEN 'Phone' WHEN o.order_type = 'takeaway' THEN 'Takeaway' "
        f"ELSE 'Dine-in' END AS name, COUNT(*) AS orders FROM orders o WHERE {week} GROUP BY name ORDER BY orders DESC")]

    cust = db.execute(
        f"SELECT COUNT(*) AS customers, COALESCE(SUM(n >= 2), 0) AS repeat_customers FROM ("
        f"SELECT COUNT(*) AS n FROM orders o WHERE {COUNTED} AND o.customer_id IS NOT NULL GROUP BY o.customer_id)").fetchone()
    rating = db.execute("SELECT COUNT(*) AS n, AVG(rating) AS avg FROM feedback").fetchone()
    return jsonify({"days": days, "busy_hours": busy, "top_week": top_week, "types": types,
                    "customers": cust["customers"], "repeat_customers": cust["repeat_customers"],
                    "ratings": rating["n"], "average_rating": round(rating["avg"], 1) if rating["avg"] else None})


@bp.route("/orders/<int:order_id>/track")
def track_order(order_id):
    """Used by the customer's page to hear "your order is ready". Returns the status and a sentence in their language."""
    db = get_db()
    row = db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if not row or (not row["confirmed_at"] and row["status"] not in AWAITING_PAYMENT + ("CANCELLED",)):
        return jsonify({"error": "Order not found"}), 404
    lang = request.args.get("lang") or row["language"] or "en-IN"
    order = dict(row)
    order["language"] = lang
    rated = db.execute("SELECT 1 FROM feedback WHERE order_id = ?", (order_id,)).fetchone() is not None
    return jsonify({"status": row["status"], "message": kitchen.customer_message(order),
                    "eta_minutes": row["eta_minutes"], "paid_online": bool(row["payment_ref"]), "rated": rated})
