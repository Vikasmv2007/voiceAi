#!/usr/bin/env python
with open('app/services/order_engine.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

print("Line 214 (index 213):", repr(lines[213]))
print("Line 215 (index 214):", repr(lines[214]))
print("Line 216 (index 215):", repr(lines[215]))
print("Line 217 (index 216):", repr(lines[216]))

# Remove the three docstring lines (indices 213, 214, 215)
# and keep the function body starting at line 217 (index 216)
new_content = ''.join(lines[:213]) + ''.join(lines[216:])

with open('app/services/order_engine.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

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