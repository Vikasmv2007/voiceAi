"""Menu API. Anyone can read it; only the owner (or the staff PIN) can change it."""
import os
import re
import time

from flask import Blueprint, current_app, jsonify, request

from app.db import get_db
from app.services import menu_matcher as mm
from app.staff import staff_only

bp = Blueprint("menu", __name__, url_prefix="/api")

TEXT_FIELDS = {"name_en": 60, "name_kn": 60, "name_hi": 60, "name_ta": 60, "name_te": 60,
               "aliases": 300, "category": 30, "description": 300, "image_url": 300, "addons": 300}
IMAGE_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
MAX_IMAGE_BYTES = 2 * 1024 * 1024


def _clean(data, creating):
    """Check the fields sent by the menu editor. Returns (values, error)."""
    out = {}
    for field, limit in TEXT_FIELDS.items():
        if field in data:
            out[field] = str(data[field] or "").strip()[:limit]
    if creating or "name_en" in out:
        if not out.get("name_en"):
            return None, "English name is required"
    if creating or "category" in out:
        if not out.get("category"):
            return None, "Category is required"
        out["category"] = out["category"][:1].upper() + out["category"][1:]
    if "image_url" in out and out["image_url"] and not re.match(r"^(https://|/static/)", out["image_url"]):
        return None, "Photo must be an https:// link or an uploaded photo"
    if "addons" in out:
        parts = [p for p in out["addons"].split(",") if p.strip()]
        parsed = mm.parse_addons({"addons": out["addons"]})
        if len(parsed) != len(parts):
            return None, "Add-ons must look like: Extra Cheese:15, Extra Chutney:10"
        out["addons"] = ", ".join(f"{n}:{p}" for n, p in parsed)
    if "price" in data or creating:
        try:
            out["price"] = int(data.get("price"))
        except (TypeError, ValueError):
            return None, "Price must be a whole number"
        if not 1 <= out["price"] <= 5000:
            return None, "Price must be between 1 and 5000"
    for flag in ("veg", "available"):
        if flag in data:
            out[flag] = 1 if data[flag] else 0
    if "stock" in data:
        if data["stock"] in (None, ""):
            out["stock"] = None                      # unlimited
        else:
            try:
                out["stock"] = int(data["stock"])
            except (TypeError, ValueError):
                return None, "Stock must be a whole number (or empty for unlimited)"
            if not 0 <= out["stock"] <= 100000:
                return None, "Stock must be 0 or more"
            if out["stock"] == 0:
                out["available"] = 0
            elif "available" not in data:
                out["available"] = 1                 # restocked
    return out, None


def _row(db, item_id):
    row = db.execute("SELECT * FROM menu_items WHERE id = ? AND active = 1", (item_id,)).fetchone()
    return dict(row) if row else None


@bp.route("/menu")
def get_menu():
    rows = get_db().execute("SELECT * FROM menu_items WHERE active = 1 ORDER BY category, id").fetchall()
    return jsonify([dict(r) for r in rows])


@bp.route("/menu", methods=["POST"])
@staff_only(role="owner")
def add_menu_item():
    values, error = _clean(request.get_json(silent=True) or {}, creating=True)
    if error:
        return jsonify({"error": error}), 400
    db = get_db()
    cols = ", ".join(values)
    cur = db.execute(f"INSERT INTO menu_items ({cols}) VALUES ({', '.join('?' * len(values))})", tuple(values.values()))
    db.commit()
    return jsonify(_row(db, cur.lastrowid)), 201


@bp.route("/menu/<int:item_id>", methods=["PATCH"])
@staff_only(role="owner")
def update_menu_item(item_id):
    """Owner changes: in/out of stock, price, names, photo, add-ons, stock count..."""
    db = get_db()
    if not _row(db, item_id):
        return jsonify({"error": "Menu item not found"}), 404
    values, error = _clean(request.get_json(silent=True) or {}, creating=False)
    if error:
        return jsonify({"error": error}), 400
    if values:
        db.execute(f"UPDATE menu_items SET {', '.join(c + ' = ?' for c in values)} WHERE id = ?",
                   (*values.values(), item_id))
        db.commit()
    return jsonify(_row(db, item_id))


@bp.route("/menu/<int:item_id>", methods=["DELETE"])
@staff_only(role="owner")
def remove_menu_item(item_id):
    """Removed from the menu, but kept in the database so old bills still show the dish."""
    db = get_db()
    if not _row(db, item_id):
        return jsonify({"error": "Menu item not found"}), 404
    db.execute("UPDATE menu_items SET active = 0, available = 0 WHERE id = ?", (item_id,))
    db.commit()
    return jsonify({"id": item_id, "removed": True})


@bp.route("/menu/<int:item_id>/image", methods=["POST"])
@staff_only(role="owner")
def upload_image(item_id):
    db = get_db()
    if not _row(db, item_id):
        return jsonify({"error": "Menu item not found"}), 404
    f = request.files.get("image")
    if not f or f.mimetype not in IMAGE_TYPES:
        return jsonify({"error": "Choose a JPG, PNG or WEBP photo"}), 400
    data = f.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        return jsonify({"error": "Photo must be smaller than 2 MB"}), 400
    folder = os.path.join(current_app.static_folder, "uploads")
    os.makedirs(folder, exist_ok=True)
    name = f"menu-{item_id}-{int(time.time())}.{IMAGE_TYPES[f.mimetype]}"
    with open(os.path.join(folder, name), "wb") as out:
        out.write(data)
    url = "/static/uploads/" + name
    db.execute("UPDATE menu_items SET image_url = ? WHERE id = ?", (url, item_id))
    db.commit()
    return jsonify(_row(db, item_id))
