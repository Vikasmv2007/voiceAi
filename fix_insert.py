#!/usr/bin/env python
with open('app/services/order_engine.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the INSERT INTO order_items - add the parameters that were lost
# Current: db.execute("INSERT INTO order_items (order_id, menu_item_id, quantity, unit_price, notes) VALUES (?, ?, ?, ?, ?)"
# Fixed:   db.execute("INSERT INTO order_items (order_id, menu_item_id, quantity, unit_price, notes) VALUES (?, ?, ?, ?, ?", (order_id, item["id"], qty, item["price"], note))

# Actually, the current state has the string closing with ?) and then nothing
# I need to add the parameters after the closing "

# Find the exact broken pattern
old = 'db.execute("INSERT INTO order_items (order_id, menu_item_id, quantity, unit_price, notes) VALUES (?, ?, ?, ?, ?)"'
new = 'db.execute("INSERT INTO order_items (order_id, menu_item_id, quantity, unit_price, notes) VALUES (?, ?, ?, ?, ?)", (order_id, item["id"], qty, item["price"], note))'

if old in content:
    content = content.replace(old, new)
    print("Fixed INSERT INTO order_items")
else:
    print("Pattern not found - trying alternative")
    # Try with different quote styles
    old2 = 'db.execute(\"INSERT INTO order_items (order_id, menu_item_id, quantity, unit_price, notes) VALUES (?, ?, ?, ?, ?)\"'
    if old2 in content:
        content = content.replace(old2, new)
        print("Fixed with alternative pattern")
    else:
        print("Alternative pattern not found either")

# Write
with open('app/services/order_engine.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Written. Testing import...")
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