import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")   # Windows consoles cannot print ₹ otherwise

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

    # --- Test 4: "yes" to the suggested drink adds it ---
    s4 = str(uuid.uuid4())
    print("\n=== Test 4: Upsell ===")
    u1 = order_engine.handle_turn(s4, "one masala dosa", "en-IN")
    assert u1["awaiting"] == "upsell"
    u2 = order_engine.handle_turn(s4, "yes", "en-IN")
    assert len(u2["cart"]["items"]) == 2, u2["reply"]
    print("Upsell passed!")

    # --- Test 5: an order said while we asked for the name is not lost ---
    s5 = str(uuid.uuid4())
    print("\n=== Test 5: Order during name question ===")
    order_engine.handle_turn(s5, "hello", "en-IN")
    n2 = order_engine.handle_turn(s5, "two idli", "en-IN")
    assert n2["cart"]["items"] and n2["reply"], n2
    assert n2["customer_name"] is None
    print("Order during name question passed!")

    # --- Test 6: spoken "takeaway" is not overwritten by the web form's default ---
    s6 = str(uuid.uuid4())
    print("\n=== Test 6: Spoken takeaway beats form default ===")
    form = dict(customer_name="Ravi", serving={"type": "dine-in", "table": None})
    for said in ("one idli", "no", "that's all", "yes", "takeaway"):
        r = order_engine.handle_turn(s6, said, "en-IN", **form)
    r = order_engine.handle_turn(s6, "9876543210", "en-IN", **form)
    assert r["awaiting"] == "payment", r["reply"]
    r = order_engine.handle_turn(s6, "upi", "en-IN", **form)
    assert r["awaiting"] == "upi_confirm" and not r["confirmed"]
    print("Takeaway passed!")

    print("\nALL TESTS PASSED!")
