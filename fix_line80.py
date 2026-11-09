#!/usr/bin/env python
with open('app/services/order_engine.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the db.execute call at line 80
# Current: db.execute("INSERT INTO order_items (order_id, menu_item_id, quantity, unit_price, notes) VALUES (?, ?, ?, ?, ?")
# Fixed:   db.execute("INSERT INTO order_items (order_id, menu_item_id, quantity, unit_price, notes) VALUES (?, ?, ?, ?, ?", (order_id, item["id"], qty, item["price"], note))

old = 'db.execute("INSERT INTO order_items (order_id, menu_item_id, quantity, unit_price, notes) VALUES (?, ?, ?, ?, ?"'
new = 'db.execute("INSERT INTO order_items (order_id, menu_item_id, quantity, unit_price, notes) VALUES (?, ?, ?, ?, ?)", (order_id, item["id"], qty, item["price"], note))'

if old in content:
    content = content.replace(old, new)
    print("Fixed db.execute call")
else:
    print("Pattern not found")
    idx = content.find('db.execute("INSERT')
    if idx >= 0:
        print(f"Found at {idx}: {repr(content[idx:idx+100])}")

with open('app/services/order_engine.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Written. Now testing import...")
import sys
sys.path.insert(0, '.')
import importlib.util
try:
    spec = importlib.util.spec_from_file_location('order_engine', 'app/services/order_engine.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    print("SUCCESS: Import works!")
except SyntaxError as e:
    print(f"Still error: {e}")
    print(f"Line: {e.lineno}, Offset: {e.offset}")