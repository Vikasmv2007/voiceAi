"""Checks your LLM settings from .env.   Run:  python -m scripts.check_llm"""
import sqlite3

from app import config
from app.services import llm

SENTENCES = [
    "I would like two masala dosa and a filter coffee please",
    "ek idli bina pyaaz ke aur ek coffee",
    "anything sweet under 50",
]

print("LLM_BASE_URL:", config.LLM_BASE_URL or "(empty)")
print("LLM_MODEL   :", config.LLM_MODEL or "(empty)")
print("LLM_MODE    :", config.LLM_MODE)
if not llm.configured():
    print("\nLLM is not configured (or LLM_MODE=off). The app will use rules only. That is fine.")
    raise SystemExit(0)

con = sqlite3.connect(config.DATABASE)
con.row_factory = sqlite3.Row
menu = [dict(r) for r in con.execute("SELECT * FROM menu_items").fetchall()]
con.close()

for s in SENTENCES:
    print("\nSaid  :", s)
    out = llm.parse_with_llm(s, menu, "en", {"cart": [], "awaiting": None})
    print("LLM ->", out if out else "no usable answer (see the [llm] line above)")
