#!/usr/bin/env python
with open('app/services/order_engine.py', 'r', encoding='utf-8') as f:
    content = f.read()

# The problem line has trailing duplicated text
# Current: 'db.execute("INSERT INTO order_items (order_id, menu_item_id, quantity, unit_price, notes) VALUES (?, ?, ?, ?, ?)", (order_id, item["id"], qty, item["price"], note))id"], qty, item["price"], note))'
# Fixed: 'db.execute("INSERT INTO order_items (order_id, menu_item_id, quantity, unit_price, notes) VALUES (?, ?, ?, ?, ?)", (order_id, item["id"], qty, item["price"], note))'

# Find the pattern with the trailing junk
import re

# Search for the db.execute INSERT line and fix it
idx = content.find('db.execute("INSERT INTO order_items (order_id, menu_item_id,')
if idx >= 0:
    # Get the full line
    line_end = content.find('\n', idx)
    full_line = content[idx:line_end]
    
    # The correct ending should be: note)) followed by \n
    # Find where note)) appears
    note_pos = full_line.rfind('note))')
    if note_pos >= 0:
        # Everything up to and including note)) is correct
        # Anything after that is junk
        junk_start = note_pos + len('note))')
        junk = full_line[junk_start:]
        print(f"Junk trailing text: {repr(junk)}")
        
        # Remove the junk
        fixed_line = full_line[:junk_start+1]  # +1 to include the newline... actually no newline in the middle
        # Actually, we need to replace the line in the content
        
        # Find the exact old string to replace
        old = full_line
        # The fixed version: remove everything after note))
        # But we need to keep the note))
        # Actually, the line should end with note))\n
        # Let me just replace the entire line
        
        # New line: same but without the trailing junk after note))
        # The line currently has: ...note))id"], qty, item["price"], note))
        # Should be: ...note))\n
        
        # Let me just find and replace the specific pattern
        new = full_line.replace('id"], qty, item["price"], note))', 'note))')
        
        if new != full_line:
            content = content.replace(old, new)
            print("Fixed trailing junk on line 80")
        else:
            print("Could not find the junk pattern to replace")
    else:
        print("Could not find note)) in the line")
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