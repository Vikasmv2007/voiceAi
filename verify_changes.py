#!/usr/bin/env python
import sys
import importlib.util
sys.path.insert(0, '.')

# Import order_engine and verify key changes
spec = importlib.util.spec_from_file_location('order_engine', 'app/services/order_engine.py')
order_engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(order_engine)

with open('app/services/order_engine.py', 'r') as f:
    content = f.read()

# Check all key patterns
checks = {
    'AWAITING_CASH statement count': content.count("UPDATE orders SET status = 'AWAITING_CASH'"),
    'No final_ok': 'final_ok' not in content,
    'No final_confirm gate': 'if not st.get("final_ok") and awaiting != "confirm"' not in content,
    'try_place function': 'def try_place()' in content,
}

print('KEY CHANGES VERIFICATION')
print('=' * 50)
for name, result in checks.items():
    marker = 'PASS' if result else 'FAIL'
    print(f'{marker}: {name}: {result}')

print()
print('SPECIFIC CHECK - try_place AWAITING_CASH branches:')
# Find the is_cash and else branches
is_cash_idx = content.find('is_cash = st.get')
if is_cash_idx >= 0:
    section = content[is_cash_idx:is_cash_idx+400]
    print(section[:300])