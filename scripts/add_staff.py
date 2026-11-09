"""Create a staff login.   Run:  python -m scripts.add_staff
Roles: owner (orders + menu + everything) or staff (orders only)."""
import getpass
import sqlite3

from app import config
from app.db import connect, ensure_schema
from app.staff import create_account

ensure_schema(config.DATABASE)
username = input("Username: ").strip()
role = (input("Role (owner/staff) [staff]: ").strip().lower() or "staff")
password = getpass.getpass("Password (min 6 characters): ")
if password != getpass.getpass("Password again: "):
    raise SystemExit("Passwords do not match. Nothing changed.")
con = connect(config.DATABASE)
try:
    create_account(con, username, password, role)
except (ValueError, sqlite3.IntegrityError) as e:
    raise SystemExit(f"Could not create the login: {e}")
print(f"Created {role} login '{username.lower()}'. Log in at /login")
