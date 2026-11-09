#!/usr/bin/env python
import re

with open('app/services/order_engine.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find all db.execute( patterns that have a newline inside the string
# Pattern: db.execute("...\\n...") or db.execute('...\\n...')
# We need to find where the string literal starts and ends

# Let me use a different approach: find all lines that have db.execute and check if the
# opening quote doesn't have a matching closing quote on the same line

lines = content.split('\n')
issues = []

for i, line in enumerate(lines, 1):
    if 'db.execute(' in line:
        # Count opening and closing quotes
        open_quotes = line.count('"')
        close_quotes = line.count('"')
        # But we need to be smarter - check if the string is continued on next line
        # Simple heuristic: if line has odd number of quotes, string continues
        # But this is too simple. Let me just check if line ends without closing the string
        
        # Check if there's a " inside the db.execute call that isn't closed
        # Find the position of db.execute(
        pos = line.find('db.execute(')
        if pos >= 0:
            substr = line[pos:]
            # Count quotes in the substring after db.execute(
            after = substr[len('db.execute('):]
            quotes = after.count('"')
            if quotes % 2 == 1:
                # Odd number of quotes - string continues to next line
                issues.append((i, line.strip()[:80], quotes))

print(f"Found {len(issues)} potential multi-line string issues in db.execute calls:")
for line_num, line_content, quote_count in issues:
    print(f"  Line {line_num}: quotes={quote_count}, content: {line_content}")