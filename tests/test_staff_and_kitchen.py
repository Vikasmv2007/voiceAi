"""Staff-only actions, logins, the kitchen flow, stock, customer cancel/feedback, bills, menu editor."""
import io

from app import config
from app.db import get_db
from app.services import notify
from app.staff import create_account
from tests.conftest import CHECKOUT, item_id, order_row


def submit(chat, pay="cash"):
    return chat(CHECKOUT + [pay] + (["confirm"] if pay == "upi" else []))[-1]


def test_customer_cannot_confirm_with_pin(client, chat, monkeypatch):
    monkeypatch.setattr(config, "STAFF_PIN", "4321")
    for pay, waiting in (("upi", "AWAITING_UPI"), ("cash", "AWAITING_CASH")):
        oid = submit(chat, pay)["order_id"]
        assert order_row(oid)["status"] == waiting
        assert client.get(f"/bill/{oid}").status_code == 404
        for status in ("CONFIRMED", "PREPARING"):
            assert client.post(f"/api/orders/{oid}/status", json={"status": status}).status_code == 401
        assert client.post(f"/api/orders/{oid}/status", json={"status": "CONFIRMED"},
                           headers={"X-Staff-Pin": "wrong"}).status_code == 401
        pin = {"X-Staff-Pin": "4321"}
        assert client.post(f"/api/orders/{oid}/status", json={"status": "PREPARING"}, headers=pin).status_code == 400
        assert client.post(f"/api/orders/{oid}/status", json={"status": "CONFIRMED"}, headers=pin).status_code == 200
        row = order_row(oid)
        assert row["status"] == "CONFIRMED" and row["confirmed_at"] and row["confirmed_by"] == "PIN"
        assert row["eta_minutes"] == config.PREP_MINUTES + (config.MINUTES_PER_ORDER_AHEAD if pay == "cash" else 0)
        assert client.get(f"/bill/{oid}").status_code == 200


def test_staff_logins_and_roles(app, client, chat):
    create_account(get_db(), "owner1", "secret123", "owner")
    create_account(get_db(), "cook", "secret123", "staff")
    assert client.get("/dashboard").status_code == 302                 # must log in
    oid = submit(chat)["order_id"]
    assert client.post(f"/api/orders/{oid}/status", json={"status": "CONFIRMED"}).status_code == 401
    assert client.post("/login", data={"username": "cook", "password": "bad"}).status_code == 200
    assert client.post("/login", data={"username": "cook", "password": "secret123"}).status_code == 302
    assert client.get("/dashboard").status_code == 200
    assert client.post(f"/api/orders/{oid}/status", json={"status": "CONFIRMED"}).status_code == 200
    assert order_row(oid)["confirmed_by"] == "cook"
    # Staff cannot edit the menu; the owner can.
    assert client.patch(f"/api/menu/{item_id('Idli')}", json={"price": 25}).status_code == 403
    client.get("/logout")
    client.post("/login", data={"username": "owner1", "password": "secret123"})
    assert client.patch(f"/api/menu/{item_id('Idli')}", json={"price": 25}).json["price"] == 25


def test_stock_goes_down_on_confirm_and_comes_back_on_cancel(client, chat):
    vada = item_id("Medu Vada")
    get_db().execute("UPDATE menu_items SET stock = 2 WHERE id = ?", (vada,))
    get_db().commit()
    r = chat(["I am Ravi", "two vada", "no", "that's all", "yes", "takeaway", "9876543210", "cash"])
    oid = r[-1]["order_id"]
    client.post(f"/api/orders/{oid}/status", json={"status": "CONFIRMED"})
    row = get_db().execute("SELECT stock, available FROM menu_items WHERE id = ?", (vada,)).fetchone()
    assert (row["stock"], row["available"]) == (0, 0)                 # sold out automatically
    client.post(f"/api/orders/{oid}/status", json={"status": "CANCELLED"})
    assert get_db().execute("SELECT stock FROM menu_items WHERE id = ?", (vada,)).fetchone()["stock"] == 2


def test_customer_cancel_and_feedback(client, chat):
    r = submit(chat)
    oid = r["order_id"]
    sid = order_row(oid)["session_id"]
    assert client.post(f"/api/orders/{oid}/customer-cancel", json={"session_id": "someone-else"}).status_code == 404
    other = submit(chat)["order_id"]
    osid = order_row(other)["session_id"]
    assert client.post(f"/api/orders/{other}/customer-cancel", json={"session_id": osid}).status_code == 200
    assert order_row(other)["status"] == "CANCELLED"
    # Once confirmed, the customer can no longer cancel; after it is served they can rate it.
    for status in ("CONFIRMED",):
        client.post(f"/api/orders/{oid}/status", json={"status": status})
    assert client.post(f"/api/orders/{oid}/customer-cancel", json={"session_id": sid}).status_code == 400
    assert client.post(f"/api/orders/{oid}/feedback", json={"session_id": sid, "rating": 5}).status_code == 400
    for status in ("PREPARING", "READY"):
        client.post(f"/api/orders/{oid}/status", json={"status": status})
    assert client.post(f"/api/orders/{oid}/feedback", json={"session_id": sid, "rating": 9}).status_code == 400
    assert client.post(f"/api/orders/{oid}/feedback",
                       json={"session_id": sid, "rating": 4, "comment": "Tasty"}).status_code == 200
    assert client.get("/api/analytics").json["average_rating"] == 4
    assert client.get(f"/api/orders/{oid}/track").json["rated"] is True


def test_messages_sent_on_status_change(client, chat, monkeypatch):
    sent = []
    monkeypatch.setattr(config, "TWILIO_ACCOUNT_SID", "AC1")
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", "t")
    monkeypatch.setattr(config, "TWILIO_SMS_FROM", "+15550001")
    monkeypatch.setattr(notify, "_send_sms", lambda to, text: sent.append((to, text)))
    monkeypatch.setattr(notify.threading, "Thread",
                        lambda target, args, daemon: type("T", (), {"start": lambda self: target(*args)})())
    oid = submit(chat)["order_id"]
    for status in ("CONFIRMED", "PREPARING", "READY"):
        client.post(f"/api/orders/{oid}/status", json={"status": status})
    assert [to for to, _ in sent] == ["919876543210", "919876543210"]   # confirmed + ready
    assert "confirmed" in sent[0][1] and "minutes" in sent[0][1] and "pickup" in sent[1][1]


def test_bill_gst_and_kot(client, chat, monkeypatch):
    monkeypatch.setattr(config, "GST_RATE", 5)
    monkeypatch.setattr(config, "GSTIN", "29ABCDE1234F1Z5")
    r = chat(["I am Ravi", "two masala dosa", "no", "that's all", "yes", "takeaway", "9876543210", "cash"])
    oid = r[-1]["order_id"]
    client.post(f"/api/orders/{oid}/status", json={"status": "CONFIRMED"})
    html = client.get(f"/bill/{oid}").get_data(as_text=True)
    for text in ("TAX INVOICE", "29ABCDE1234F1Z5", "CGST @ 2.5%", "SGST @ 2.5%", "₹120", "₹126", f"{oid:06d}"):
        assert text in html
    kot = client.get(f"/kot/{oid}").get_data(as_text=True)
    assert "KOT #" in kot and "2 × Masala Dosa" in kot and "₹" not in kot


def test_menu_editor(client):
    r = client.post("/api/menu", json={"name_en": "Paneer Roll", "category": "snacks", "price": 90, "veg": True,
                                       "addons": "Extra Cheese:20", "stock": "5", "description": "Grilled paneer wrap."})
    assert r.status_code == 201 and r.json["category"] == "Snacks" and r.json["stock"] == 5
    new_id = r.json["id"]
    assert client.post("/api/menu", json={"name_en": "", "category": "x", "price": 1}).status_code == 400
    assert client.post("/api/menu", json={"name_en": "X", "category": "x", "price": 1,
                                          "addons": "cheese twenty"}).status_code == 400
    assert client.patch(f"/api/menu/{new_id}", json={"image_url": "javascript:alert(1)"}).status_code == 400
    png = io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"0" * 100)
    up = client.post(f"/api/menu/{new_id}/image", data={"image": (png, "p.png", "image/png")},
                     content_type="multipart/form-data")
    assert up.status_code == 200 and up.json["image_url"].startswith("/static/uploads/menu-")
    assert client.delete(f"/api/menu/{new_id}").status_code == 200
    assert new_id not in [m["id"] for m in client.get("/api/menu").json]


def test_new_dish_and_category_work_in_chat(client, chat):
    client.post("/api/menu", json={"name_en": "Mango Juice", "category": "Juices", "price": 50})
    r = chat(["any juices?", "one mango juice"])
    assert "Mango Juice" in r[0]["reply"]
    assert r[1]["cart"]["items"][0]["name"] == "Mango Juice"


def test_rate_limit(client, monkeypatch):
    monkeypatch.setattr(config, "RATE_LIMIT_VOICE", 3)
    codes = [client.post("/api/tts", json={"text": ""}).status_code for _ in range(5)]
    assert codes[:3] == [400, 400, 400] and codes[3:] == [429, 429]
    assert client.post("/api/tts", json={"text": "x" * 700}).status_code == 429


def test_pages_load(client):
    for url in ("/", "/dashboard", "/dashboard/tables", "/login", "/health", "/api/menu", "/api/orders/live",
                "/api/orders/history", "/api/stats", "/api/analytics", "/api/me"):
        assert client.get(url).status_code == 200, url
