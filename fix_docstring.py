#!/usr/bin/env python
with open('app/services/order_engine.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the multi-line docstring in try_place() with a single-line version
# Old: three lines of docstring with line breaks
# New: single-line docstring

old_doc_pattern = '        "The customer has said yes to the order. We collect any missing\n        details (name, table/where, phone number, payment mode, UPI confirmation),\n        re-check stock, and then (and only then) send the order to the kitchen.\n        Returns the new \'awaiting\' value.\n        nonlocal confirmed\n        lines_now = _lines(db, order_id)'

# simpler approach: just find and replace the specific lines
# Let me just replace lines 239-242 area

# Find the try_place function and fix the docstring
idx = content.find('def try_place():')
if idx >= 0:
    # Show context
    print(f"Found try_place at {idx}")
    # Find the end of the docstring (look for nonlocal confirmed or the actual code)
    end_idx = content.find('nonlocal confirmed', idx)
    if end_idx >= 0:
        # Get the section from def try_place to nonlocal confirmed
        section = content[idx:end_idx]
        print(f"Section length: {len(section)}")
        print(f"Section starts: {repr(section[:100])}")
        print(f"Section ends: {repr(section[-50:])}")
        
        # Now replace the multi-line docstring with single line
        # The old docstring spans from after 'def try_place():' to before 'nonlocal confirmed'
        # We need to replace the content between them
        
        # Find where the docstring starts (the opening " after def try_place:)
        doc_start = content.find('"', idx + len('def try_place():'))
        if doc_start >= 0:
            # Find the closing " of the docstring
            # It should be before 'nonlocal confirmed'
            doc_end = content.find('"', doc_start + 1)
            while doc_end >= 0 and content[doc_end-1] == '\\':
                # escaped quote, look for next one
                doc_end = content.find('"', doc_end + 1)
            
            if doc_end >= 0:
                print(f"Docstring from {doc_start} to {doc_end}")
                old_doc = content[doc_start:doc_end+1]
                # Replace with single-line docstring
                new_doc = '        "The customer has said yes to the order. We collect any missing details (name, table/where, phone number, payment mode, UPI confirmation), re-check stock, and then (and only then) send the order to the kitchen. Returns the new \'awaiting\' value. nonlocal confirmed"'
                
                if old_doc in content:
                    content = content.replace(old_doc, new_doc)
                    print("Replaced docstring")
                else:
                    print("Old doc pattern not found exactly")
            else:
                print("Could not find closing quote of docstring")
        else:
            print("Could not find 'nonlocal confirmed'")
    else:
        print("Could not find 'nonlocal confirmed'")
else:
    print("Could not find def try_place()")

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