import sqlite3
from flask import g, current_app


def connect(path):
    con = sqlite3.connect(path, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def get_db():
    if "db" not in g:
        g.db = connect(current_app.config["DATABASE"])
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    with current_app.open_resource("schema.sql") as f:
        db.executescript(f.read().decode("utf-8"))


# Columns added after the first version. ensure_schema() adds any that are missing,
# so an existing restaurant.db keeps its menu and old orders.
NEW_COLUMNS = {
    "orders": [
        ("customer_id", "TEXT"), ("channel", "TEXT DEFAULT 'web'"), ("customer_name", "TEXT"),
        ("customer_phone", "TEXT"), ("payment_mode", "TEXT"), ("subtotal", "INTEGER DEFAULT 0"),
        ("tax", "INTEGER DEFAULT 0"), ("payment_ref", "TEXT"), ("gateway_qr_id", "TEXT"),
        ("confirmed_by", "TEXT"), ("eta_minutes", "INTEGER"),
    ],
    "menu_items": [
        ("name_ta", "TEXT"), ("name_te", "TEXT"), ("image_url", "TEXT DEFAULT ''"),
        ("addons", "TEXT DEFAULT ''"), ("stock", "INTEGER"), ("active", "INTEGER DEFAULT 1"),
    ],
    "order_items": [("addons", "TEXT DEFAULT ''")],
}
NEW_TABLES = """
CREATE TABLE IF NOT EXISTS sessions (session_id TEXT PRIMARY KEY, state TEXT NOT NULL,
                                     updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS feedback (order_id INTEGER PRIMARY KEY, rating INTEGER NOT NULL,
                                     comment TEXT DEFAULT '', created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                                     FOREIGN KEY (order_id) REFERENCES orders(id));
CREATE TABLE IF NOT EXISTS staff (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE,
                                  password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'staff',
                                  created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_orders_session ON orders(session_id);
"""


def ensure_schema(path):
    """Brings an existing restaurant.db up to date (safe to run every start).
    Your menu and old orders are NOT touched."""
    con = sqlite3.connect(path)
    try:
        if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='orders'").fetchone():
            return              # database not created yet (seed_menu will create it)
        for table, columns in NEW_COLUMNS.items():
            have = {r[1] for r in con.execute(f"PRAGMA table_info({table})")}
            for column, ddl in columns:
                if column not in have:
                    con.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
        con.executescript(NEW_TABLES)
        # Old orders: subtotal was not stored separately.
        con.execute("UPDATE orders SET subtotal = total WHERE subtotal = 0 AND tax = 0 AND total > 0")
        con.commit()
    finally:
        con.close()
