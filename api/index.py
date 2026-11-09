"""Vercel entry point: Vercel runs this file and calls the Flask app named `app`."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402
from app.db import get_db, init_db  # noqa: E402
from app.seed_menu import seed  # noqa: E402

app = create_app()

# First start on a new server: create the tables and the starter menu (never touches existing data).
with app.app_context():
    import sqlite3
    con = sqlite3.connect(app.config["DATABASE"])
    exists = con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='menu_items'").fetchone()
    con.close()
    if not exists:
        init_db()
        seed(get_db())
