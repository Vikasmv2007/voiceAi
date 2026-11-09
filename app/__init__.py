import secrets
from datetime import timedelta

from flask import Flask, render_template
from werkzeug.middleware.proxy_fix import ProxyFix

from app import config
from app.db import close_db, ensure_schema


def create_app(test_config=None):
    app = Flask(__name__)
    app.json.ensure_ascii = False
    app.config.update(
        DATABASE=config.DATABASE,
        SECRET_KEY=config.SECRET_KEY or secrets.token_hex(32),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
        MAX_CONTENT_LENGTH=5 * 1024 * 1024,        # uploads (voice clips, menu photos)
    )
    if test_config:
        app.config.update(test_config)
    if config.TRUST_PROXY:
        # Behind nginx / Caddy / Render: trust their X-Forwarded-* headers (real IP, https).
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    app.teardown_appcontext(close_db)
    ensure_schema(app.config["DATABASE"])
    _warn_about_setup()

    from app import staff
    from app.routes import bill, menu, orders, payments, phone, voice
    for module in (menu, orders, voice, bill, phone, payments, staff):
        app.register_blueprint(module.bp)

    @app.route("/")
    def index():
        return render_template("index.html", restaurant=config.RESTAURANT_NAME)

    @app.route("/dashboard")
    def dashboard():
        return staff.page_guard() or render_template("dashboard.html", restaurant=config.RESTAURANT_NAME)

    @app.route("/dashboard/tables")
    def table_qr_codes():
        """Printable QR codes, one per table: scanning opens the order page with the table filled in."""
        return staff.page_guard() or render_template("tables.html", restaurant=config.RESTAURANT_NAME,
                                                     base=config.PUBLIC_BASE_URL)

    @app.route("/health")
    def health():
        return {"status": "ok"}

    return app


def _warn_about_setup():
    if not config.SECRET_KEY:
        print("[warning] SECRET_KEY is not set in .env: staff are logged out whenever the server restarts.")
    if not config.STAFF_PIN:
        print("[warning] STAFF_PIN is not set in .env. Unless you create staff logins "
              "(python -m scripts.add_staff), anyone who can open the site can confirm orders.")
