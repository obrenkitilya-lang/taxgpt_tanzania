#!/usr/bin/env python3
FILE = '/workspaces/taxgpt_tanzania/app.py'
with open(FILE, 'r') as f:
    content = f.read()

OLD = '7. Never provide legal advice — only tax information. Recommend a registered tax consultant for complex disputes.\n"""'
NEW = '''7. Never provide legal advice — only tax information. Recommend a registered tax consultant for complex disputes.
8. TOOL SUGGESTIONS: After answering any question, suggest the most relevant sidebar tool using this mapping:
   - Calculations (PAYE, VAT, SDL, WCF, CIT) -> "Use our Calculator tool in the sidebar for instant calculations."
   - Tax deadlines or filing dates -> "See our Deadlines tool in the sidebar for a full compliance calendar."
   - TRA/KRA/URA notices, letters, or documents -> "Upload your document in our Documents tool for detailed analysis."
   - Business registration or company setup -> "Visit our Business Setup tool in the sidebar for step-by-step guidance."
   - Latest news, budget, or law changes -> "Check our Tax Updates tool for the latest news."
   - Only suggest ONE most relevant tool per response.
"""'''

if OLD in content:
    content = content.replace(OLD, NEW)
    print('Tool suggestions rule added')
else:
    start = content.find('7. Never provide legal advice')
    end = content.find('"""', start) + 3
    content = content[:start] + NEW[NEW.find('7.'):] + content[end:]
    print('Tool suggestions rule added (marker-based)')

with open(FILE, 'w') as f:
    f.write(content)
print('Saved')
