import os
import sys

from app import create_app
from app.services import order_engine
import uuid

app = create_app()
with app.app_context():
    # --- Test 1: Full Flow with UPI ---
    sess = str(uuid.uuid4())
    print("=== Test 1: Full Flow with UPI ===")
    t1 = order_engine.handle_turn(sess, "Hello", "en-IN")
    assert t1["awaiting"] == "name"

    t2 = order_engine.handle_turn(sess, "My name is Rahul", "en-IN")
    assert t2["customer_name"] == "Rahul"

    t3 = order_engine.handle_turn(sess, "Two masala dosa", "en-IN")
    t4 = order_engine.handle_turn(sess, "That is all", "en-IN")
    t5 = order_engine.handle_turn(sess, "yes", "en-IN")
    t6 = order_engine.handle_turn(sess, "dine in table 4", "en-IN")
    assert t6["awaiting"] == "phone"

    t7 = order_engine.handle_turn(sess, "9876543210", "en-IN")
    assert t7["customer_phone"] == "9876543210"
    assert t7["awaiting"] == "payment"

    t8 = order_engine.handle_turn(sess, "UPI scanner", "en-IN")
    assert t8["awaiting"] == "upi_confirm"
    assert t8["confirmed"] is False
    assert t8["upi"] is not None
    assert "upi://pay" in t8["upi"]["uri"]

    t9 = order_engine.handle_turn(sess, "confirm", "en-IN")
    assert t9["confirmed"] is True
    print("UPI flow passed! Confirmed Order ID:", t9["order_id"])

    # --- Test 2: Full Flow with Cash ---
    sess2 = str(uuid.uuid4())
    print("\n=== Test 2: Full Flow with Cash ===")
    order_engine.handle_turn(sess2, "I am Priya", "en-IN")
    order_engine.handle_turn(sess2, "One idli and one filter coffee", "en-IN")
    order_engine.handle_turn(sess2, "confirm order", "en-IN")
    order_engine.handle_turn(sess2, "takeaway", "en-IN")
    order_engine.handle_turn(sess2, "9123456789", "en-IN")
    t_cash = order_engine.handle_turn(sess2, "cash", "en-IN")
    assert t_cash["confirmed"] is True
    assert t_cash["payment_mode"] == "cash"
    print("Cash flow passed! Confirmed Order ID:", t_cash["order_id"])

    # --- Test 3: Hindi Language Flow ---
    sess3 = str(uuid.uuid4())
    print("\n=== Test 3: Hindi Flow ===")
    h1 = order_engine.handle_turn(sess3, "नमस्ते", "hi-IN")
    assert h1["awaiting"] == "name"
    assert "नाम" in h1["reply"]
    h2 = order_engine.handle_turn(sess3, "मेरा नाम विकास है", "hi-IN")
    assert h2["customer_name"] == "Vikas"
    print("Hindi flow passed!")

    print("\nALL TESTS PASSED!")
