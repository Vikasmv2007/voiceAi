#!/usr/bin/env python
with open('app/services/order_engine.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Issue 1: Line 80 - INSERT INTO order_items
# Current broken: db.execute("INSERT INTO order_items (order_id, menu_item_id, quantity, unit_price, notes) VALUES (?, ?, ?, ?, ?" (?, ?, ?, ?, ?", (order_id,
# Fixed: single line with complete string and parameters

fix1_old = 'db.execute("INSERT INTO order_items (order_id, menu_item_id, quantity, unit_price, notes) VALUES (?, ?, ?, ?, ?"'
fix1_new = 'db.execute("INSERT INTO order_items (order_id, menu_item_id, quantity, unit_price, notes) VALUES (?, ?, ?, ?, ?)", (order_id, item["id"], qty, item["price"], note))'

if fix1_old in content:
    content = content.replace(fix1_old, fix1_new)
    print(f"Fixed issue 1 (INSERT INTO order_items)")
else:
    print("Issue 1 pattern not found")

# Issue 2 & 3: Lines 286-291 and 293-298 - UPDATE orders SET status = 'AWAITING_CASH'
# These have the string split across lines with parameters on following lines

# Pattern for the first one (around line 286-291)
# db.execute("UPDATE orders SET status = 'AWAITING_CASH', language = ?, order_type = ?, table_no = ?,
#               customer_id = ?, channel = ?, customer_name = ?, customer_phone = ?,
#               payment_mode = ? WHERE id = ?",
#              (language_code, sv["type"], sv["table"], customer_id, channel,
#               st.get("customer_name"), st.get("customer_phone"), st.get("payment_mode"), order_id))

# Fix: combine into single line with the full SQL and parameters

# Find and replace the first UPDATE (there are two, we'll do both)
# The pattern starts with db.execute("UPDATE orders SET status = 'AWAITING_CASH'

# Let me find the exact patterns
idx1 = content.find("db.execute(\"UPDATE orders SET status = 'AWAITING_CASH', language = ?, order_type = ?, table_no")
if idx1 >= 0:
    print(f"Found first UPDATE pattern at {idx1}")
    # Show context
    print(f"  Context: {repr(content[idx1:idx1+150])}")
else:
    print("First UPDATE pattern not found")

idx2 = content.find("db.execute(\"UPDATE orders SET status = 'AWAITING_CASH', language = ?, order_type = ?, table_no", 3000)
if idx2 >= 0:
    print(f"Found second UPDATE pattern at {idx2}")
    print(f"  Context: {repr(content[idx2:idx2+150])}")
else:
    print("Second UPDATE pattern not found")

# Now let me fix both by replacing the multi-line patterns with single-line versions
# The fixed version should have the full SQL on one line followed by the parameters

# Fix pattern for UPDATE statements - combine SQL and parameters on one line
fix2_old_pattern1 = '''db.execute("UPDATE orders SET status = 'AWAITING_CASH', language = ?, order_type = ?, table_no = ?,
                          customer_id = ?, channel = ?, customer_name = ?, customer_phone = ?,
                          payment_mode = ? WHERE id = ?",
                       (language_code, sv["type"], sv["table"], customer_id, channel,
                        st.get("customer_name"), st.get("customer_phone"), st.get("payment_mode"), order_id))'''

fix2_new_pattern1 = '''db.execute("UPDATE orders SET status = 'AWAITING_CASH', language = ?, order_type = ?, table_no = ?, customer_id = ?, channel = ?, customer_name = ?, customer_phone = ?, payment_mode = ? WHERE id = ?", (language_code, sv["type"], sv["table"], customer_id, channel, st.get("customer_name"), st.get("customer_phone"), st.get("payment_mode"), order_id))'''

# Try to find and replace
if fix2_old_pattern1 in content:
    content = content.replace(fix2_old_pattern1, fix2_new_pattern1)
    print("Fixed first UPDATE pattern")
else:
    print("First UPDATE pattern not found exactly")

# Second one - need to find it differently
# Let me search for the specific text that's unique to the second occurrence
idx_for_second = content.find("st.get(\"customer_name\"), st.get(\"customer_phone\"), st.get(\"payment_mode\"), order_id))")
if idx_for_second >= 0:
    # Work backwards to find the db.execute
    start = content.rfind('db.execute("UPDATE orders SET status = \'AWAITING_CASH\', language = ?, order_type = ?, table_no', 0, idx_for_second)
    if start >= 0:
        print(f"Found second UPDATE start at {start}")
        end = idx_for_second + len("st.get(\"customer_name\"), st.get(\"customer_phone\"), st.get(\"payment_mode\"), order_id))")
        old_section = content[start:end]
        print(f"  Old section: {repr(old_section[:150])}")
        
        new_section = '''db.execute("UPDATE orders SET status = 'AWAITING_CASH', language = ?, order_type = ?, table_no = ?, customer_id = ?, channel = ?, customer_name = ?, customer_phone = ?, payment_mode = ? WHERE id = ?", (language_code, sv["type"], sv["table"], customer_id, channel, st.get("customer_name"), st.get("customer_phone"), st.get("payment_mode"), order_id))'''
        
        if old_section in content:
            content = content.replace(old_section, new_section)
            print("Fixed second UPDATE pattern")
        else:
            print("Second UPDATE section not found for replacement")
    else:
        print("Could not find second UPDATE start")
else:
    print("Could not find the ending pattern for second UPDATE")

# Write the result
with open('app/services/order_engine.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("File written. Testing import...")
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