"""
migrate_to_supabase.py
──────────────────────
Reads all products from Google Sheets and inserts them into Supabase.
Also migrates the Transacation (transaction log) sheet.

BEFORE RUNNING:
1. Open Supabase → SQL Editor → paste and run the CREATE TABLE statements
   from the top of sheets.py (or use the block below).
2. Make sure your .env has SUPABASE_URL and SUPABASE_KEY filled in.
3. Run: python migrate_to_supabase.py

──────────────────────────────────────────────────────
SQL to run in Supabase SQL Editor FIRST:
──────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS products (
  id          SERIAL PRIMARY KEY,
  product_id  TEXT UNIQUE,
  brand       TEXT NOT NULL DEFAULT '',
  spec        TEXT DEFAULT '',
  type_       TEXT DEFAULT '',
  quantity    INTEGER DEFAULT 0,
  rate        NUMERIC DEFAULT 0,
  total       NUMERIC DEFAULT 0,
  status      TEXT DEFAULT 'No Stock',
  unit        TEXT DEFAULT 'nos',
  category    TEXT DEFAULT '',
  sort_order  INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS transactions (
  id           SERIAL PRIMARY KEY,
  timestamp    TIMESTAMPTZ DEFAULT NOW(),
  type_        TEXT,
  brand        TEXT,
  spec         TEXT,
  qty_change   INTEGER,
  stock_before INTEGER,
  stock_after  INTEGER,
  vehicle_no   TEXT DEFAULT '',
  operator     TEXT DEFAULT '',
  party        TEXT DEFAULT ''
);

──────────────────────────────────────────────────────
"""

import os
import sys
import json
import time
from dotenv import load_dotenv

load_dotenv()


# ── Validate env ──────────────────────────────────────────────────
REQUIRED = ["TELEGRAM_TOKEN", "GROQ_API_KEY", "GOOGLE_SHEET_ID",
            "GOOGLE_CREDENTIALS_JSON", "SUPABASE_URL", "SUPABASE_KEY"]
missing = [k for k in REQUIRED if not os.environ.get(k)]
if missing:
    print(f"❌ Missing env vars: {', '.join(missing)}")
    print("Fill in your .env file and try again.")
    sys.exit(1)


# ── Google Sheets client ──────────────────────────────────────────
import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def _gs_client():
    raw = os.environ["GOOGLE_CREDENTIALS_JSON"].replace("\\\\n", "\\n")
    creds_dict = json.loads(raw)
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return gspread.authorize(creds)

def _get_sheet(name):
    gc  = _gs_client()
    spr = gc.open_by_key(os.environ["GOOGLE_SHEET_ID"])
    try:
        return spr.worksheet(name)
    except gspread.WorksheetNotFound:
        return None


# ── Supabase client ───────────────────────────────────────────────
from supabase import create_client

def _sb_client():
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])


# ── Category detection (mirrors original logic) ───────────────────
CATEGORY_MAP = {
    "solar panel": "Solar Panel",
    "inverter":    "Inverter",
    "acdb/dcdb":   "ACDB/DCDB",
    "acdb":        "ACDB/DCDB",
    "cable":       "Cable",
    "cables":      "Cable",
    "pvc material":"PVC Material",
    "structure":   "Structure",
}

def _detect_section(col_b_text: str) -> str | None:
    """Returns canonical section name if col_b looks like a section header."""
    t = col_b_text.strip().lower()
    for kw, section in CATEGORY_MAP.items():
        if kw in t:
            return section
    return None


# ── Main migration ────────────────────────────────────────────────
def migrate_products():
    print("\n📊 Reading Stock sheet from Google Sheets...")
    ws = _get_sheet("Stock")
    if not ws:
        print("❌ 'Stock' sheet not found.")
        return

    rows = ws.get_all_values()
    print(f"   {len(rows)} rows fetched.")

    sb = _sb_client()

    # Clear existing products table to avoid duplicates on re-run
    print("🗑  Clearing existing products table...")
    sb.table("products").delete().neq("id", 0).execute()

    current_section = "General"
    sort_order      = 0
    inserted        = 0
    skipped         = 0

    for i, row in enumerate(rows):
        # Pad short rows
        while len(row) < 9:
            row.append("")

        pid   = str(row[0]).strip()   # col A = product_id
        brand = str(row[1]).strip()   # col B = Brand
        spec  = str(row[2]).strip()   # col C = Spec
        type_ = str(row[3]).strip()   # col D = Type
        qty_s = str(row[4]).strip()   # col E = Quantity
        rate_s= str(row[5]).strip()   # col F = Rate
        tot_s = str(row[6]).strip()   # col G = Total
        stat  = str(row[7]).strip()   # col H = Status
        unit  = str(row[8]).strip()   # col I = Unit

        # Section header row: no product_id, col_b has section keyword
        if not pid and brand:
            sec = _detect_section(brand)
            if sec:
                current_section = sec
                print(f"   📁 Section: {current_section}")
            skipped += 1
            continue

        # Skip if no product_id (blank row, column header, etc.)
        if not pid or pid == "product_id":
            skipped += 1
            continue

        # Skip if brand looks like a column header
        if brand.lower() in {"brand/product", "brand", "product", "sr.no", "sr no"}:
            skipped += 1
            continue

        # Parse numbers
        try:    qty  = int(qty_s)
        except: qty  = 0
        try:    rate = float(str(rate_s).replace(",", "").replace("₹", "") or 0)
        except: rate = 0.0
        try:    total = float(str(tot_s).replace(",", "").replace("₹", "") or 0)
        except: total = 0.0

        if not stat:
            stat = "No Stock" if qty == 0 else ("Low Stock" if qty < 5 else "In Stock")
        if not unit:
            unit = "nos"

        sort_order += 1
        record = {
            "product_id": pid,
            "brand":      brand,
            "spec":       spec,
            "type_":      type_,
            "quantity":   qty,
            "rate":       rate,
            "total":      total,
            "status":     stat,
            "unit":       unit,
            "category":   current_section,
            "sort_order": sort_order,
        }

        try:
            sb.table("products").insert(record).execute()
            print(f"   ✅ [{sort_order:03d}] {pid} — {brand} {spec} {type_} | qty={qty}")
            inserted += 1
        except Exception as e:
            print(f"   ❌ Row {i+2}: {pid} — {brand}: {e}")
            skipped += 1

        # Small pause to avoid Supabase rate limits
        time.sleep(0.05)

    print(f"\n✅ Products migration done: {inserted} inserted, {skipped} skipped.\n")


def migrate_transactions():
    print("📋 Reading Transacation sheet from Google Sheets...")
    ws = _get_sheet("Transacation")
    if not ws:
        print("   ⚠️  'Transacation' sheet not found — skipping transactions.")
        return

    rows = ws.get_all_values()
    if len(rows) < 2:
        print("   No transaction data found.")
        return

    print(f"   {len(rows) - 1} transaction rows fetched.")

    sb = _sb_client()
    print("🗑  Clearing existing transactions table...")
    sb.table("transactions").delete().neq("id", 0).execute()

    inserted = 0
    skipped  = 0

    for row in rows[1:]:   # skip header row
        # Old format: A=product_id(blank), B=Timestamp, C=Type, D=Brand, E=Spec,
        #             F=Qty Change, G=Before, H=After, I=Vehicle, J=Operator, K=Party
        while len(row) < 11:
            row.append("")

        timestamp  = str(row[1]).strip()
        type_      = str(row[2]).strip()
        brand      = str(row[3]).strip()
        spec       = str(row[4]).strip()
        qty_change = str(row[5]).strip()
        before     = str(row[6]).strip()
        after      = str(row[7]).strip()
        vehicle    = str(row[8]).strip()
        operator   = str(row[9]).strip()
        party      = str(row[10]).strip()

        if not type_:
            skipped += 1
            continue

        try:    qty_change = int(qty_change)
        except: qty_change = 0
        try:    before = int(before)
        except: before = 0
        try:    after  = int(after)
        except: after  = 0

        # Parse IST timestamp to ISO format
        ts_iso = None
        for fmt in ("%Y-%m-%d %H:%M:%S IST", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S"):
            try:
                from datetime import datetime, timezone, timedelta
                IST = timezone(timedelta(hours=5, minutes=30))
                dt = datetime.strptime(timestamp.replace(" IST",""), fmt.replace(" IST",""))
                ts_iso = dt.replace(tzinfo=IST).isoformat()
                break
            except:
                continue

        record = {
            "timestamp":    ts_iso or timestamp,
            "type_":        type_,
            "brand":        brand,
            "spec":         spec,
            "qty_change":   qty_change,
            "stock_before": before,
            "stock_after":  after,
            "vehicle_no":   vehicle,
            "operator":     operator,
            "party":        party,
        }

        try:
            sb.table("transactions").insert(record).execute()
            inserted += 1
        except Exception as e:
            print(f"   ❌ Transaction row: {type_} {brand}: {e}")
            skipped += 1

        time.sleep(0.03)

    print(f"✅ Transactions migration done: {inserted} inserted, {skipped} skipped.\n")


def verify():
    print("🔍 Verifying Supabase data...")
    sb = _sb_client()

    prod_resp = sb.table("products").select("id", count="exact").execute()
    txn_resp  = sb.table("transactions").select("id", count="exact").execute()

    print(f"   products table    : {len(prod_resp.data)} rows")
    print(f"   transactions table: {len(txn_resp.data)} rows")

    # Show a few sample products
    sample = sb.table("products").select("product_id,brand,spec,quantity,category") \
               .order("sort_order").limit(5).execute()
    print("\n   Sample products:")
    for p in sample.data:
        print(f"   [{p['product_id']}] {p['brand']} {p['spec']} — qty={p['quantity']} ({p['category']})")

    print("\n✅ Verification complete. Bot is ready to use Supabase.\n")


if __name__ == "__main__":
    print("=" * 60)
    print("  GURUKRIPA ENTERPRISES — Supabase Migration")
    print("=" * 60)

    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--products-only",     action="store_true")
    parser.add_argument("--transactions-only", action="store_true")
    parser.add_argument("--verify-only",       action="store_true")
    args = parser.parse_args()

    if args.verify_only:
        verify()
    elif args.products_only:
        migrate_products()
        verify()
    elif args.transactions_only:
        migrate_transactions()
    else:
        # Full migration
        migrate_products()
        migrate_transactions()
        verify()
