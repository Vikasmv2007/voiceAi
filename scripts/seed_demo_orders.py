"""Adds about a week of FAKE finished orders so the analytics charts have something to show.
Run:  python -m scripts.seed_demo_orders        (to remove them later: python -m scripts.reset_orders)
Use only for testing / screenshots. Do not present demo numbers as real sales."""
import random
import sqlite3
from datetime import datetime, timedelta, timezone

from app import config
from app.db import ensure_schema

if input("This adds FAKE demo orders for the last 7 days. Type YES to continue: ").strip() != "YES":
    raise SystemExit("Cancelled. Nothing changed.")

ensure_schema(config.DATABASE)
rng = random.Random(7)                      # same fake data every time
con = sqlite3.connect(config.DATABASE)
con.row_factory = sqlite3.Row
menu = [dict(r) for r in con.execute("SELECT id, price, category FROM menu_items")]
if not menu:
    raise SystemExit("The menu is empty. Run: python -m app.seed_menu  (first time only).")

HOURS = [8, 9, 9, 10, 12, 13, 13, 14, 16, 17, 19, 20, 20, 21]   # busy around breakfast, lunch and dinner (IST)
customers = [f"demo-customer-{i}" for i in range(1, 13)]
now_ist = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
count = 0
for days_ago in range(6, -1, -1):
    for _ in range(rng.randint(6, 14)):
        when_ist = (now_ist - timedelta(days=days_ago)).replace(
            hour=rng.choice(HOURS), minute=rng.randint(0, 59), second=0, microsecond=0)
        if when_ist > now_ist:
            continue
        when_utc = (when_ist - timedelta(hours=5, minutes=30)).strftime("%Y-%m-%d %H:%M:%S")
        kind = rng.choices(["dine-in", "takeaway", "phone"], [5, 3, 2])[0]
        lines = rng.sample(menu, rng.randint(1, 3))
        total = 0
        cur = con.execute(
            """INSERT INTO orders (session_id, status, language, order_type, table_no, total, created_at,
                                   confirmed_at, customer_id, channel) VALUES (?, 'DELIVERED', ?, ?, ?, 0, ?, ?, ?, ?)""",
            (f"demo-{count}", rng.choice(["en-IN", "en-IN", "hi-IN", "kn-IN"]),
             "dine-in" if kind == "dine-in" else "takeaway", str(rng.randint(1, 10)) if kind == "dine-in" else None,
             when_utc, when_utc, rng.choice(customers), "phone" if kind == "phone" else "web"))
        for m in lines:
            qty = rng.randint(1, 3)
            total += qty * m["price"]
            con.execute("INSERT INTO order_items (order_id, menu_item_id, quantity, unit_price) VALUES (?, ?, ?, ?)",
                        (cur.lastrowid, m["id"], qty, m["price"]))
        con.execute("UPDATE orders SET total = ? WHERE id = ?", (total, cur.lastrowid))
        count += 1
con.commit()
con.close()
print(f"Added {count} demo orders. Open the dashboard > Analytics tab.")
