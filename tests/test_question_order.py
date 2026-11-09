"""The agent asks in this order: name -> phone -> order -> table -> UPI/QR or cash -> confirm."""
import uuid

from app.services import order_engine


def test_name_phone_order_table_payment(chat):
    # The web page always sends "dine-in" (its order-type box) and no name / phone / payment.
    form = dict(serving={"type": "dine-in", "table": None})
    r = chat(["hello", "My name is Vikas", "8073487816", "two masala dosa", "no", "that's all", "yes",
              "5", "QR", "confirm"], **form)
    assert r[0]["awaiting"] == "name" and "name" in r[0]["reply"]
    assert r[1]["awaiting"] == "phone" and "phone number" in r[1]["reply"] and r[1]["customer_name"] == "Vikas"
    assert r[2]["awaiting"] is None and "order" in r[2]["reply"] and r[2]["customer_phone"] == "8073487816"
    assert r[3]["cart"]["items"][0]["quantity"] == 2
    assert r[5]["awaiting"] == "confirm"
    assert r[6]["awaiting"] == "table" and "table" in r[6]["reply"]
    assert r[7]["awaiting"] == "payment" and "Cash or UPI" in r[7]["reply"]
    assert r[8]["awaiting"] == "upi_confirm" and "QR" in r[8]["reply"]
    assert r[9]["submitted"] and r[9]["status"] == "AWAITING_UPI"


def test_cash_after_table(chat):
    form = dict(serving={"type": "dine-in", "table": None})
    r = chat(["hi", "I am Asha", "9123456789", "one idli", "no", "that's all", "yes", "table 3", "cash"], **form)
    assert r[7]["awaiting"] == "payment"
    assert r[8]["submitted"] and r[8]["status"] == "AWAITING_CASH"


def test_phone_said_later_still_works(chat):
    # Customer ignores the phone question and orders straight away: the order is kept,
    # and the phone number is asked again at checkout (after the table).
    form = dict(serving={"type": "dine-in", "table": None})
    r = chat(["hello", "I am Ravi", "two idli", "no", "that's all", "yes", "table 2"], **form)
    assert r[1]["awaiting"] == "phone"
    assert r[2]["cart"]["items"][0]["quantity"] == 2
    assert r[-1]["awaiting"] == "phone"
