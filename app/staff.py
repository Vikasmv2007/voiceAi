"""Who is staff? Two ways, use either:

1. Staff accounts (recommended): create them with  python -m scripts.add_staff
   Staff log in at /login. Roles: "owner" (everything) and "staff" (orders only).
   Each confirmation records who did it (orders.confirmed_by).
2. A shared STAFF_PIN in .env, sent by the dashboard in the X-Staff-Pin header.

If neither is set up, staff actions are open (a warning is printed at start).
"""
import hmac
from functools import wraps

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from app import config
from app.db import get_db
from app.ratelimit import allow

bp = Blueprint("staff", __name__)


def accounts_exist(db=None):
    db = db or get_db()
    return db.execute("SELECT 1 FROM staff LIMIT 1").fetchone() is not None


def current_staff():
    """{"name", "role"} of whoever is acting, or None."""
    if session.get("staff"):
        return {"name": session["staff"], "role": session.get("role", "staff")}
    if config.STAFF_PIN:
        given = request.headers.get("X-Staff-Pin", "")
        if given and hmac.compare_digest(given.encode(), config.STAFF_PIN.encode()):
            return {"name": "PIN", "role": "owner"}
    return None


def protection_on():
    return bool(config.STAFF_PIN) or accounts_exist()


def staff_only(view=None, role=None):
    """@staff_only for staff actions, @staff_only(role="owner") for owner-only ones (menu)."""
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if protection_on():
                who = current_staff()
                if not who:
                    return jsonify({"error": "Staff login or PIN required", "staff_pin": bool(config.STAFF_PIN),
                                    "login": accounts_exist()}), 401
                if role == "owner" and who["role"] != "owner":
                    return jsonify({"error": "Only the owner can do this"}), 403
            return fn(*args, **kwargs)
        return wrapper
    return deco(view) if view else deco


def staff_name():
    who = current_staff()
    return who["name"] if who else None


def page_guard():
    """For dashboard pages: redirect to /login when accounts exist and nobody is logged in."""
    if accounts_exist() and not session.get("staff"):
        return redirect(url_for("staff.login", next=request.path))
    return None


def create_account(db, username, password, role="staff"):
    if role not in ("owner", "staff"):
        raise ValueError("role must be owner or staff")
    if len(password) < 6:
        raise ValueError("password must be at least 6 characters")
    db.execute("INSERT INTO staff (username, password_hash, role) VALUES (?, ?, ?)",
               (username.strip().lower(), generate_password_hash(password), role))
    db.commit()


@bp.route("/login", methods=["GET", "POST"])
def login():
    error = None
    nxt = request.values.get("next") or "/dashboard"
    if not nxt.startswith("/") or nxt.startswith("//"):
        nxt = "/dashboard"
    if request.method == "POST":
        if not allow("login", 10):
            error = "Too many tries. Wait a minute."
        else:
            username = (request.form.get("username") or "").strip().lower()
            row = get_db().execute("SELECT * FROM staff WHERE username = ?", (username,)).fetchone()
            if row and check_password_hash(row["password_hash"], request.form.get("password") or ""):
                session.clear()
                session["staff"], session["role"] = row["username"], row["role"]
                session.permanent = True
                return redirect(nxt)
            error = "Wrong username or password."
    return render_template("login.html", error=error, next=nxt)


@bp.route("/logout", methods=["POST", "GET"])
def logout():
    session.clear()
    return redirect(url_for("staff.login"))


@bp.route("/api/me")
def me():
    who = current_staff()
    return jsonify({"staff": who, "accounts": accounts_exist(), "pin": bool(config.STAFF_PIN)})
