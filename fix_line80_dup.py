#!/usr/bin/env python
with open('app/services/order_engine.py', 'r', encoding='utf-8') as f:
    content = f.read()

# The problem: line 80 has duplicated content
# Current (from earlier output):
# '        db.execute("INSERT INTO order_items (order_id, menu_item_id, quantity, unit_price, notes) VALUES (?, ?, ?, ?, ?)", (order_id, item["id"], qty, item["price"], note)) (?, ?, ?, ?, ?)", (order_id, item["'

# Fixed: just the clean db.execute call
old = 'db.execute("INSERT INTO order_items (order_id, menu_item_id, quantity, unit_price, notes) VALUES (?, ?, ?, ?, ?)", (order_id, item["id"], qty, item["price"], note)) (?, ?, ?, ?, ?)", (order_id, item["'
new = 'db.execute("INSERT INTO order_items (order_id, menu_item_id, quantity, unit_price, notes) VALUES (?, ?, ?, ?, ?)", (order_id, item["id"], qty, item["price"], note))'

if old in content:
    content = content.replace(old, new)
    print("Fixed duplicated content on line 80")
else:
    print("Pattern not found, trying alternative")
    # Try just finding and replacing the specific broken line
    idx = content.find('db.execute("INSERT INTO order_items (order_id, menu_item_id,')
    if idx >= 0:
        print(f"Found at {idx}: {repr(content[idx:idx+100])}")
        
        # Find where the line ends (next db.execute or end of function)
        # Look for the next db.execute or a new line that ends the statement
        next_db = content.find('db.execute', idx + 1)
        if next_db >= 0:
            # Get everything between idx and next_db
            section = content[idx:next_db]
            print(f"Section to next db.execute: {repr(section[:150])}")
        else:
            # Find db.commit or def or class
            for marker in ['db.commit()', 'def _', 'def handle', 'class ']:
                pos = content.find(marker, idx)
                if pos >= 0:
                    print(f"Found {marker} at {pos}")
                    break
    else:
        print("Could not find the INSERT pattern")

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