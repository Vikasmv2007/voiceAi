"""Only the staff may confirm orders or change the menu (they send the STAFF_PIN)."""
import hmac
from functools import wraps

from flask import jsonify, request

from app import config


def staff_only(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if config.STAFF_PIN:
            given = request.headers.get("X-Staff-Pin", "")
            if not hmac.compare_digest(given.encode(), config.STAFF_PIN.encode()):
                return jsonify({"error": "Staff PIN required", "staff_pin": True}), 401
        return view(*args, **kwargs)
    return wrapper
