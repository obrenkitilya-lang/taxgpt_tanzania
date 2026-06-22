FILE = '/workspaces/taxgpt_tanzania/app.py'
with open(FILE, 'r') as f:
    content = f.read()

OLD = '2. For CALCULATIONS: you know Tanzania\'s tax rates well — use them confidently. Tanzania PAYE bands (monthly): 0% on 0-270,000; 8% on 270,001-520,000; 20% on 520,001-760,000; 25% on 760,001-1,000,000; 30% above 1,000,000. VAT: 18%. SDL: 4% of gross payroll. WCF: 0.5%. Corporate tax: 30%. Always show step-by-step workings.'
NEW = '''2. For CALCULATIONS: use these Tanzania rates — they are correct, do NOT override them with your training data.
   PAYE PROCEDURE (monthly): Step 1 — deduct NSSF (10% of gross, max 100,000 TZS) to get taxable income. Step 2 — apply these MONTHLY bands to taxable income:
     Band 1: TZS 0 – 270,000 → 0%
     Band 2: TZS 270,001 – 520,000 → 8%  (max 20,000)
     Band 3: TZS 520,001 – 760,000 → 20% (max 48,000)
     Band 4: TZS 760,001 – 1,000,000 → 25% (max 60,000)
     Band 5: Above 1,000,000 → 30%
   WORKED EXAMPLE — Gross 1,000,000 TZS: NSSF=100,000 → Taxable=900,000 → PAYE=(0+20,000+48,000+35,000)=103,000 → Net Pay=797,000.
   OTHER RATES: VAT 18%. SDL 4% of gross payroll. WCF 0.5%. Corporate tax 30%. Always show step-by-step workings.'''

if OLD in content:
    content = content.replace(OLD, NEW)
    print('PAYE fix applied')
else:
    # marker-based: find rule 2 line
    start = content.find('2. For CALCULATIONS:')
    end = content.find('\n   3.', start)
    if end == -1:
        end = content.find('\n3.', start)
    content = content[:start] + NEW + content[end:]
    print('PAYE fix applied (marker-based)')

with open(FILE, 'w') as f:
    f.write(content)
print('Saved')
