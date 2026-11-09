"""Test helpers: every test gets a fresh database with the starter menu and all optional services off."""
import uuid

import pytest

from app import config, create_app
from app.db import get_db, init_db
from app.ratelimit import reset
from app.seed_menu import seed


@pytest.fixture
def app(tmp_path, monkeypatch):
    # Every test: a fresh database and every optional service switched off.
    for name, value in {"STAFF_PIN": "", "GST_RATE": 0, "RAZORPAY_KEY_ID": "", "RAZORPAY_KEY_SECRET": "",
                        "RAZORPAY_WEBHOOK_SECRET": "", "WHATSAPP_TOKEN": "", "WHATSAPP_PHONE_NUMBER_ID": "",
                        "TWILIO_ACCOUNT_SID": "", "TWILIO_AUTH_TOKEN": "", "TWILIO_SMS_FROM": "",
                        "LLM_BASE_URL": "", "SECRET_KEY": "test-secret"}.items():
        monkeypatch.setattr(config, name, value)
    reset()
    application = create_app({"DATABASE": str(tmp_path / "test.db"), "TESTING": True, "SECRET_KEY": "test"})
    with application.app_context():
        init_db()
        seed(get_db())
    with application.app_context():
        yield application


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def chat(app):
    """chat(["one idli", "yes"], ...) -> list of replies, all in one conversation."""
    from app.services import order_engine

    def run(turns, lang="en-IN", session=None, **kw):
        session = session or str(uuid.uuid4())
        return [order_engine.handle_turn(session, t, lang, **kw) for t in turns]
    return run


def item_id(name):
    return get_db().execute("SELECT id FROM menu_items WHERE name_en = ?", (name,)).fetchone()["id"]


def order_row(order_id):
    return get_db().execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()


CHECKOUT = ["I am Ravi", "one idli", "no", "that's all", "yes", "takeaway", "9876543210"]
