from flask import Flask, render_template
from app import config
from app.db import close_db, ensure_schema


def create_app():
    app = Flask(__name__)
    app.json.ensure_ascii = False
    app.config["DATABASE"] = config.DATABASE
    app.teardown_appcontext(close_db)
    ensure_schema(config.DATABASE)

    from app.routes import bill, menu, orders, phone, voice
    app.register_blueprint(menu.bp)
    app.register_blueprint(orders.bp)
    app.register_blueprint(voice.bp)
    app.register_blueprint(bill.bp)
    app.register_blueprint(phone.bp)

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/dashboard")
    def dashboard():
        return render_template("dashboard.html")

    @app.route("/health")
    def health():
        return {"status": "ok"}

    return app