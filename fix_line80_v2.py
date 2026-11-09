#!/usr/bin/env python
with open('app/services/order_engine.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Current broken state (line 80-81):
# Line 80:         db.execute("INSERT INTO order_items (order_id, menu_item_id, quantity, unit_price, notes) VALUES (?, ?, ?, ?, ?")
# Line 81:                 (?, ?, ?, ?, ?", (order_id,

# We need to fix it to:
# db.execute("INSERT INTO order_items (order_id, menu_item_id, quantity, unit_price, notes) VALUES (?, ?, ?, ?, ?)", (order_id, item["id"], qty, item["price"], note))

# Find the exact pattern currently in the file
idx = content.find('db.execute("INSERT INTO order_items (order_id, menu_item_id, quantity, unit_price, notes) VALUES (?, ?, ?, ?, ?"')
if idx >= 0:
    print(f"Found broken pattern at {idx}: {repr(content[idx:idx+120])}")
else:
    print("Broken pattern not found exactly, searching...")
    idx = content.find('db.execute("INSERT INTO order_items')
    if idx >= 0:
        print(f"Found at {idx}: {repr(content[idx:idx+120])}")

# Fix: replace the broken concatenation with the proper single line
# The fix is to combine line 80 and the first part of line 81 into one complete line

# Let me just rewrite the specific section
# We need to find "db.execute("INSERT INTO order_items" and fix it

# Strategy: replace from "db.execute(" through the end of that db.execute call
# The original had: db.execute("INSERT INTO order_items (order_id, menu_item_id, quantity, unit_price, notes) VALUES (?, ?, ?, ?, ?", (order_id, item["id"], qty, item["price"], note))

# Let me just fix it by replacing the entire broken section
search_str = 'db.execute("INSERT INTO order_items (order_id, menu_item_id, quantity, unit_price, notes) VALUES (?, ?, ?, ?, ?"'
replace_str = 'db.execute("INSERT INTO order_items (order_id, menu_item_id, quantity, unit_price, notes) VALUES (?, ?, ?, ?, ?)", (order_id, item["id"], qty, item["price"], note))'

if search_str in content:
    content = content.replace(search_str, replace_str)
    print("Fixed the db.execute call")
else:
    print("Search string not found - trying alternative")
    # Try finding just the execute line and fixing from there
    idx = content.find('db.execute("INSERT')
    if idx >= 0:
        # Find the end of this db.execute call
        end_idx = content.find('db.commit()', idx)
        if end_idx >= 0:
            section = content[idx:end_idx]
            print(f"Section from db.execute to db.commit: {repr(section[:150])}")
        else:
            print("No db.commit found after")

# Write
with open('app/services/order_engine.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Written")
print("Now testing import...")
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