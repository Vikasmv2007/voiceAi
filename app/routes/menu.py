from flask import Blueprint, jsonify, request
from app.db import get_db

bp = Blueprint("menu", __name__, url_prefix="/api")


@bp.route("/menu")
def get_menu():
    rows = get_db().execute("SELECT * FROM menu_items ORDER BY category, id").fetchall()
    return jsonify([dict(r) for r in rows])


@bp.route("/menu/<int:item_id>", methods=["PATCH"])
def update_menu_item(item_id):
    """Owner changes: mark a dish in/out of stock, or change its price."""
    data = request.get_json(silent=True) or {}
    db = get_db()
    if not db.execute("SELECT id FROM menu_items WHERE id = ?", (item_id,)).fetchone():
        return jsonify({"error": "Menu item not found"}), 404
    if "available" in data:
        db.execute("UPDATE menu_items SET available = ? WHERE id = ?",
                   (1 if data["available"] else 0, item_id))
    if "price" in data:
        try:
            price = int(data["price"])
        except (TypeError, ValueError):
            return jsonify({"error": "Price must be a whole number"}), 400
        if not 1 <= price <= 5000:
            return jsonify({"error": "Price must be between 1 and 5000"}), 400
        db.execute("UPDATE menu_items SET price = ? WHERE id = ?", (price, item_id))
    db.commit()
    row = db.execute("SELECT * FROM menu_items WHERE id = ?", (item_id,)).fetchone()
    return jsonify(dict(row))