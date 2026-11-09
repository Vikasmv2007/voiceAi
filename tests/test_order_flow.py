"""The conversation: ordering, the rules of checkout, languages, add-ons, stock, GST."""
import uuid

from app import config
from tests.conftest import CHECKOUT, item_id, order_row


def test_upi_flow_is_only_submitted(chat):
    r = chat(["Hello", "My name is Rahul", "Two masala dosa", "That is all", "yes", "dine in table 4",
              "9876543210", "UPI scanner", "confirm"])
    assert r[0]["awaiting"] == "name" and r[1]["customer_name"] == "Rahul"
    assert r[5]["awaiting"] == "phone" and r[6]["awaiting"] == "payment"
    assert r[7]["awaiting"] == "upi_confirm" and "upi://pay" in r[7]["upi"]["uri"]
    last = r[-1]
    assert last["submitted"] and not last["confirmed"] and last["status"] == "AWAITING_UPI"
    assert order_row(last["order_id"])["confirmed_at"] is None


def test_cash_flow_waits_for_staff(chat):
    r = chat(["I am Priya", "One idli and one filter coffee", "confirm order", "takeaway", "9123456789", "cash"])
    assert r[-1]["submitted"] and r[-1]["status"] == "AWAITING_CASH" and not r[-1]["confirmed"]
    assert r[-1]["reply"].count("₹") == 1              # amount said once, not twice


def test_hindi_name(chat):
    r = chat(["नमस्ते", "मेरा नाम विकास है"], lang="hi-IN")
    assert r[0]["awaiting"] == "name" and "नाम" in r[0]["reply"]
    assert r[1]["customer_name"] == "Vikas"


def test_upsell_yes_adds_drink(chat):
    r = chat(["one masala dosa", "yes"])
    assert r[0]["awaiting"] == "upsell" and len(r[1]["cart"]["items"]) == 2


def test_order_during_name_question_is_kept(chat):
    r = chat(["hello", "two idli"])
    assert r[1]["cart"]["items"] and r[1]["customer_name"] is None


def test_spoken_takeaway_beats_form_default(chat):
    form = dict(customer_name="Ravi", serving={"type": "dine-in", "table": None})
    r = chat(["one idli", "no", "that's all", "yes", "takeaway", "9876543210", "upi"], **form)
    assert r[5]["awaiting"] == "payment" and r[6]["awaiting"] == "upi_confirm"


def test_add_item_while_paying(chat):
    r = chat(CHECKOUT + ["upi", "also one coffee"])
    assert len(r[-1]["cart"]["items"]) == 2 and r[-1]["awaiting"] == "confirm"


def test_paid_addons_raise_the_price(chat):
    r = chat(["one masala dosa with extra butter", "add cheese"])
    line = r[1]["cart"]["items"][0]
    assert line["addons"] == "Extra Butter, Cheese" and line["unit_price"] == 60 + 15 + 25
    assert "Extra Butter" in r[0]["reply"]


def test_addon_for_wrong_dish_is_ignored(chat):
    r = chat(["one idli with cheese"])               # cheese is only offered on masala dosa
    assert r[0]["cart"]["items"][0]["unit_price"] == 20


def test_describe_dish(chat):
    r = chat(["what is pongal", "is masala dosa spicy", "one masala dosa less spicy"])
    assert r[0]["intent"] == "describe" and "moong dal" in r[0]["reply"]
    assert r[1]["intent"] == "describe" and not r[1]["cart"]["items"]
    assert r[2]["intent"] == "order"


def test_tamil_auto_detected(chat):
    r = chat(["வணக்கம்", "என் பெயர் ரவி", "இரண்டு இட்லி", "தோசை"])   # English selected, Tamil spoken
    assert all(x["language"] == "ta-IN" for x in r)
    assert r[1]["customer_name"] == "ரவி"
    assert r[2]["cart"]["items"][0]["quantity"] == 2
    assert r[3]["awaiting"] == "clarify"


def test_telugu(chat):
    r = chat(["నమస్కారం", "నా పేరు రవి", "రెండు ఇడ్లీ"], lang="te-IN")
    assert "పేరు" in r[0]["reply"] and r[2]["cart"]["items"][0]["quantity"] == 2


def test_stock_limit(app, chat):
    from app.db import get_db
    get_db().execute("UPDATE menu_items SET stock = 2 WHERE id = ?", (item_id("Medu Vada"),))
    get_db().commit()
    r = chat(["three vada", "two vada"])
    assert "only 2" in r[0]["reply"] and not r[0]["cart"]["items"]
    assert r[1]["cart"]["items"][0]["quantity"] == 2


def test_gst_added_on_top(chat, monkeypatch):
    monkeypatch.setattr(config, "GST_RATE", 5)
    r = chat(["two masala dosa", "no", "that's all"])
    cart = r[-1]["cart"]
    assert (cart["subtotal"], cart["tax"], cart["total"]) == (120, 6, 126)
    assert "₹126" in r[-1]["reply"]


def test_conversation_survives_restart(app, chat):
    s = str(uuid.uuid4())
    chat(["I am Ravi", "one idli"], session=s)
    from app.db import get_db
    assert get_db().execute("SELECT 1 FROM sessions WHERE session_id = ?", (s,)).fetchone()
    r = chat(["yes"], session=s)                     # state is read back from the database
    assert len(r[0]["cart"]["items"]) == 2           # the upsell "yes" still worked


def test_removed_dish_cannot_be_ordered(app, chat):
    from app.db import get_db
    get_db().execute("UPDATE menu_items SET active = 0, available = 0 WHERE name_en = 'Upma'")
    get_db().commit()
    r = chat(["one upma"])
    assert not r[0]["cart"]["items"]


def test_phone_typed_in_form_is_used(chat):
    session = str(uuid.uuid4())
    r = chat(["I am Ravi", "one idli", "no", "that's all", "yes", "takeaway"], session=session)
    assert r[-1]["awaiting"] == "phone"
    # The customer typed the number into the phone box; the page sends it with the next turn.
    nxt = chat(["ok"], session=session, customer_phone="9876543210")[0]
    assert nxt["awaiting"] == "payment"
