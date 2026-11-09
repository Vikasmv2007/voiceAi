#!/usr/bin/env python
# Script to fix multi-line string literals in order_engine.py

with open('app/services/order_engine.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix 1: The _lines function - multi-line SQL SELECT
# Old: split across lines 44-47
# New: single line
old_lines1 = '''    rows = db.execute(\n        "SELECT oi.id AS line_id, oi.menu_item_id, oi.quantity, oi.unit_price, oi.notes,\n                  m.name_en, m.name_kn, m.name_hi\n           FROM order_items oi JOIN menu_items m ON m.id = oi.menu_item_id\n           WHERE oi.order_id = ? ORDER BY oi.id", (order_id,)).fetchall()'''

new_lines1 = '''    rows = db.execute("SELECT oi.id AS line_id, oi.menu_item_id, oi.quantity, oi.unit_price, oi.notes, m.name_en, m.name_kn, m.name_hi FROM order_items oi JOIN menu_items m ON m.id = oi.menu_item_id WHERE oi.order_id = ? ORDER BY oi.id", (order_id,)).fetchall()'''

if old_lines1 in content:
    content = content.replace(old_lines1, new_lines1)
    print("Fixed _lines SQL string")
else:
    print("_lines SQL pattern not found")

# Fix 2: The _add function - multi-line UPDATE
old_add1 = '''    if gone:\n            for l in gone:\n                parts.append(say(lang, "stock_removed", name=_name(l, lang)))\n            _save_total(db, order_id)\n            if _lines(db, order_id):\n                parts.append(read_back())\n                return "confirm"\n            parts.append(say(lang, "empty_ask"))\n            return None\n\n        # 1. Customer Name\n        if not st.get("customer_name"):'''

new_add1 = '''    if gone:\n            for l in gone:\n                parts.append(say(lang, "stock_removed", name=_name(l, lang)))\n            _save_total(db, order_id)\n            if _lines(db, order_id):\n                parts.append(read_back())\n                return "confirm"\n            parts.append(say(lang, "empty_ask"))\n            return None

        # 1. Customer Name\n        if not st.get("customer_name"):'''

if old_add1 in content:
    content = content.replace(old_add1, new_add1)
    print("Fixed _add SQL string")
else:
    print("_add SQL pattern not found")

# Fix 3: The _add function - multi-line INSERT
old_add2 = '''    else:\n        db.execute("UPDATE order_items SET quantity = quantity + ?, notes = ? WHERE id = ?",\n                   (qty, new_note, line["line_id"]))'''

new_add2 = '''    else:\n        db.execute("UPDATE order_items SET quantity = quantity + ?, notes = ? WHERE id = ?", (qty, new_note, line["line_id"]))'''

if old_add2 in content:
    content = content.replace(old_add2, new_add2)
    print("Fixed _add UPDATE string")
else:
    print("_add UPDATE pattern not found")

# Write the fixed content
with open('app/services/order_engine.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("File written. Attempting import...")

# Try to import
import sys
sys.path.insert(0, '.')
import importlib.util
try:
    spec = importlib.util.spec_from_file_location('order_engine', 'app/services/order_engine.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    print("SUCCESS: Import works!")
except SyntaxError as e:
    print(f"Still has SyntaxError: {e}")
    print(f"Line: {e.lineno}, Offset: {e.offset}")