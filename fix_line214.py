#!/usr/bin/env python
with open('app/services/order_engine.py', 'r', encoding='utf-8') as f:
    content = f.read()

# The issue: line 214 starts a multi-line string that Python can't parse
# Fix: replace the string with a single-line version

# First, let me find the exact location and content
idx = content.find('        "The customer has said yes to the order. We collect any missing')
if idx >= 0:
    print("Found at", idx)

    # Now find where this string ends (look for nonlocal confirmed)
    nc_idx = content.find('nonlocal confirmed', idx)
    if nc_idx >= 0:
        print("nonlocal confirmed at", nc_idx)
        # Find the opening " after idx
        open_quote = content.find('"', idx)
        if open_quote >= 0 and open_quote < nc_idx:
            # Replace from open_quote to nc_idx with single-line string
            old_section = content[open_quote:nc_idx]
            new_section = (
                "        \"The customer has said yes to the order. "
                "We collect any missing details (name, table/where, phone number, "
                "payment mode, UPI confirmation), re-check stock, and then (and only "
                "then) send the order to the kitchen. Returns the new 'awaiting' value. "
                "nonlocal confirmed\""
            )

            if old_section in content:
                content = content.replace(old_section, new_section)
                print("Replaced string section")
            else:
                print("Old section not found exactly")
                broken = '        "The customer has said yes to the order. We collect any missing'
                fixed = '        "The customer has said yes to the order. We collect any missing details (name, table/where, phone number, payment mode, UPI confirmation), re-check stock, and then (and only then) send the order to the kitchen. Returns the new \'awaiting\' value. nonlocal confirmed"'
                if broken in content:
                    content = content.replace(broken, fixed)
                    print("Used fallback replacement")
                else:
                    print("Broken pattern not found either")
        else:
            print("Could not find nonlocal confirmed")
    else:
        print("Could not find nonlocal confirmed")
else:
    print("Could not find the string start")

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
    print("Still error:", e)
    print("Line:", e.lineno, "Offset:", e.offset)