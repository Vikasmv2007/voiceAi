import sqlite3
from flask import g, current_app

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_db():
    db = get_db()
    with current_app.open_resource("schema.sql") as f:
        db.executescript(f.read().decode("utf-8"))


def ensure_schema(path):
    """Adds the newer columns to an existing restaurant.db (safe to run every start).
    Your menu and old orders are NOT touched."""
    con = sqlite3.connect(path)
    try:
        have = {r[1] for r in con.execute("PRAGMA table_info(orders)")}
        if not have:            # database not created yet (seed_menu will create it)
            return
        for column, ddl in (
            ("customer_id", "TEXT"),
            ("channel", "TEXT DEFAULT 'web'"),
            ("customer_name", "TEXT"),
            ("customer_phone", "TEXT"),
            ("payment_mode", "TEXT"),
        ):
            if column not in have:
                con.execute(f"ALTER TABLE orders ADD COLUMN {column} {ddl}")
        con.execute("CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id)")
        con.commit()
    finally:
        con.close()
