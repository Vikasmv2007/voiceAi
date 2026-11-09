"""Deletes all orders (keeps the menu).   Run:  python -m scripts.reset_orders"""
import sqlite3
from app import config

if input("This deletes ALL orders (menu is kept). Type YES to continue: ").strip() != "YES":
    raise SystemExit("Cancelled. Nothing changed.")
con = sqlite3.connect(config.DATABASE)
con.execute("DELETE FROM order_items")
con.execute("DELETE FROM orders")
con.commit()
con.close()
print("Done. Orders cleared.")
