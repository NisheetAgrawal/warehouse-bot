"""
reset_for_production.py
────────────────────────
Resets Supabase data for a clean production go-live:
  1. Deletes ALL rows from the transactions table
  2. Sets quantity = 0 and status = 'No Stock' for EVERY product

Does NOT touch: products list, categories, brands, rates, units, sort_order.
Run once before handing the system to the warehouse team.

Usage:
  python reset_for_production.py
  python reset_for_production.py --dry-run   ← shows what would happen, no changes
"""

import os, sys
from dotenv import load_dotenv
load_dotenv()

for key in ("SUPABASE_URL", "SUPABASE_KEY"):
    if not os.environ.get(key):
        print(f"❌  Missing env var: {key}")
        sys.exit(1)

from supabase import create_client

DRY_RUN = "--dry-run" in sys.argv

def _sb():
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])


def main():
    sb = _sb()

    print("=" * 55)
    print("  GURUKRIPA ENTERPRISES — Production Reset")
    print("=" * 55)
    if DRY_RUN:
        print("  ⚠️  DRY RUN — no changes will be made\n")

    # ── 1. Count before ──────────────────────────────────────────
    txn_resp  = sb.table("transactions").select("id", count="exact").execute()
    prod_resp = sb.table("products").select("id,product_id,quantity,status").execute()

    txn_count  = len(txn_resp.data)
    prod_count = len(prod_resp.data)
    non_zero   = sum(1 for p in prod_resp.data if (p.get("quantity") or 0) != 0)

    print(f"\n📊 Current state:")
    print(f"   Transactions : {txn_count} rows")
    print(f"   Products     : {prod_count} rows total ({non_zero} with qty > 0)")

    if not DRY_RUN:
        confirm = input(
            f"\n⚠️  This will:\n"
            f"   • DELETE all {txn_count} transaction rows\n"
            f"   • Set qty=0 + status='No Stock' on all {prod_count} products\n\n"
            f"   Type 'RESET' to confirm: "
        ).strip()
        if confirm != "RESET":
            print("\n❌  Aborted — nothing changed.")
            sys.exit(0)

    # ── 2. Delete all transactions ────────────────────────────────
    print(f"\n🗑  {'[DRY RUN] Would delete' if DRY_RUN else 'Deleting'} {txn_count} transactions...")
    if not DRY_RUN:
        # Delete in chunks to avoid timeout on large tables
        deleted = 0
        while True:
            batch = sb.table("transactions").select("id").limit(500).execute()
            if not batch.data:
                break
            ids = [r["id"] for r in batch.data]
            sb.table("transactions").delete().in_("id", ids).execute()
            deleted += len(ids)
            print(f"   Deleted {deleted}/{txn_count}...")
            if len(ids) < 500:
                break
        print(f"   ✅ Transactions cleared ({deleted} rows deleted)")

    # ── 3. Reset all product quantities ──────────────────────────
    print(f"\n📦 {'[DRY RUN] Would reset' if DRY_RUN else 'Resetting'} {prod_count} product quantities...")
    if not DRY_RUN:
        # Update all products in one call
        sb.table("products").update({
            "quantity": 0,
            "total":    0,
            "status":   "No Stock",
        }).neq("id", 0).execute()      # neq("id", 0) matches every row
        print(f"   ✅ All {prod_count} products set to qty=0 / No Stock")

    # ── 4. Verify ─────────────────────────────────────────────────
    if not DRY_RUN:
        print(f"\n🔍 Verifying...")
        txn_after  = sb.table("transactions").select("id", count="exact").execute()
        prod_after = sb.table("products").select("quantity,status").execute()
        remaining_txn     = len(txn_after.data)
        non_zero_after    = sum(1 for p in prod_after.data if (p.get("quantity") or 0) != 0)
        wrong_status      = sum(1 for p in prod_after.data if p.get("status") != "No Stock")

        print(f"   Transactions remaining : {remaining_txn}  (expected 0)")
        print(f"   Products with qty > 0  : {non_zero_after}  (expected 0)")
        print(f"   Products with wrong status : {wrong_status}  (expected 0)")

        if remaining_txn == 0 and non_zero_after == 0 and wrong_status == 0:
            print(f"\n✅ Reset complete — system ready for production go-live.")
        else:
            print(f"\n⚠️  Verification found unexpected values — check manually.")
    else:
        print(f"\n✅ Dry run complete — rerun without --dry-run to apply changes.")


if __name__ == "__main__":
    main()
