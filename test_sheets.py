"""Test Google Sheets connection and product matching."""
from dotenv import load_dotenv
load_dotenv()

from sheets import _get_sheet, _is_product_row, find_product_row, get_stock, _get_or_create_transactions_sheet

print("=== Testing Google Sheets connection ===\n")

ws = _get_sheet("Stock")
if not ws:
    print("❌ Could not open Sheet1")
    exit(1)

all_rows = ws.get_all_values()
print(f"✅ Connected. Total rows in Sheet1: {len(all_rows)}\n")

print("=== Valid product rows detected ===")
count = 0
for i, row in enumerate(all_rows):
    if _is_product_row(row):
        print(f"  Row {i+1}: {row[1]} | {row[2]} | {row[3]} | Qty={row[4] if len(row)>4 else '?'}")
        count += 1
print(f"\nTotal valid products: {count}\n")

print("=== Test: Find Waaree 575 DCR ===")
idx, row = find_product_row("Waaree", "575", "DCR")
if idx:
    print(f"✅ Found at row {idx}: {row}")
else:
    print("❌ Not found")

print("\n=== Test: get_stock Waaree 575 DCR ===")
info = get_stock("Waaree", "575", "DCR")
print(info)

print("\n=== Test: TRANSACTIONS sheet ===")
txn = _get_or_create_transactions_sheet()
print(f"✅ TRANSACTIONS sheet ready: {txn.title}")
