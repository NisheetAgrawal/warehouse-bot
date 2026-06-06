"""
sheets.py — Supabase backend (drop-in replacement for Google Sheets version).
All public function signatures are identical to the gspread version so bot.py
needs zero changes.

Supabase table schema (run once in Supabase SQL Editor):
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

from supabase import create_client, Client
from datetime import datetime, timezone, timedelta
import logging
import time

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))

# ── Supabase client singleton ─────────────────────────────────────
_supabase_client: Client = None

def _get_client() -> Client:
    global _supabase_client
    if _supabase_client is None:
        from config import SUPABASE_URL, SUPABASE_KEY
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase_client


# ── Row-list conversion ───────────────────────────────────────────
# Internal format mirrors old gspread row lists so all helpers work unchanged:
#   index 0 = product_id
#   index 1 = brand
#   index 2 = spec
#   index 3 = type_
#   index 4 = quantity  (string, as gspread returned strings)
#   index 5 = rate      (string)
#   index 6 = total     (string)
#   index 7 = status
#   index 8 = unit
#   index 9 = db id     (int — used as row_idx for UPDATE calls)

def _row_to_list(p: dict) -> list:
    return [
        str(p.get("product_id", "") or ""),
        str(p.get("brand",      "") or ""),
        str(p.get("spec",       "") or ""),
        str(p.get("type_",      "") or ""),
        str(int(p.get("quantity", 0) or 0)),
        str(p.get("rate",  "") or ""),
        str(p.get("total", "") or ""),
        str(p.get("status","") or ""),
        str(p.get("unit",  "nos") or "nos"),
        p.get("id", 0),          # int, not string
    ]


# ── Short-lived row cache (15 sec) ────────────────────────────────
_rows_cache: list = []
_rows_ts:    float = 0.0
_ROWS_TTL:   int   = 15

def _get_all_rows() -> list:
    """Return cached product rows (15-second TTL). One DB read per burst."""
    global _rows_cache, _rows_ts
    if time.time() - _rows_ts < _ROWS_TTL and _rows_cache:
        return _rows_cache
    try:
        resp = _get_client().table("products").select("*").order("sort_order").execute()
        _rows_cache = [_row_to_list(p) for p in resp.data]
        _rows_ts    = time.time()
    except Exception as e:
        logger.error(f"_get_all_rows failed: {e}")
    return _rows_cache

def _invalidate_rows_cache():
    global _rows_ts
    _rows_ts = 0.0


# ── Product catalog cache (5 min) ─────────────────────────────────
_catalog_cache: list = []
_catalog_ts:    float = 0.0
_CATALOG_TTL:   int   = 300

def get_live_catalog() -> list:
    """
    Returns list of dicts: {product_id, brand, spec, type_, unit, qty}
    Cached for 5 minutes.
    """
    global _catalog_cache, _catalog_ts
    if time.time() - _catalog_ts < _CATALOG_TTL and _catalog_cache:
        return _catalog_cache

    rows = _get_all_rows()
    catalog = []
    for row in rows:
        pid   = row[0].strip() if row[0] else ""
        brand = row[1].strip() if len(row) > 1 else ""
        spec  = row[2].strip() if len(row) > 2 else ""
        type_ = row[3].strip() if len(row) > 3 else ""
        qty_s = row[4].strip() if len(row) > 4 else ""
        unit  = row[8].strip() if len(row) > 8 and isinstance(row[8], str) else ""
        if not pid or not brand:
            continue
        try:    qty = int(qty_s)
        except: qty = 0
        catalog.append({"product_id": pid, "brand": brand, "spec": spec,
                        "type_": type_, "unit": unit, "qty": qty})

    _catalog_cache = catalog
    _catalog_ts    = time.time()
    logger.info(f"Catalog refreshed: {len(catalog)} products")
    return catalog


def catalog_as_prompt_text() -> str:
    """Compact product list for Groq prompt injection."""
    cat = get_live_catalog()
    lines = []
    for p in cat:
        parts = [x for x in [p["brand"], p["spec"], p["type_"]] if x]
        lines.append(f'{p["product_id"]}: {" | ".join(parts)} ({p["unit"]})')
    return "\n".join(lines)


# ── Constants (kept for any external callers) ─────────────────────
HEADER_KEYWORDS = {
    "solar panel", "inverter", "acdb/dcdb", "cable", "cables", "dc cable",
    "ac cable", "ac cable 4sx2c", "earthing cable", "pvc material",
    "brand", "sr.no", "sr no", "category", "watt", "kw", "product",
    "meters", "pcs", "quantity", "stock status", "rate", "total"
}

HEADER_SPEC_KEYWORDS = {
    "watt", "kw", "meter", "meters", "pcs", "spec", "quantity",
    "stock status", "rate", "total", "type"
}

CATEGORY_HEADERS = {
    "solar panel":  "Solar Panel",
    "solar":        "Solar Panel",
    "panel":        "Solar Panel",
    "inverter":     "Inverter",
    "acdb":         "ACDB/DCDB",
    "dcdb":         "ACDB/DCDB",
    "acdb/dcdb":    "ACDB/DCDB",
    "cable":        "Cable",
    "cables":       "Cable",
    "wire":         "Cable",
    "pvc":          "PVC Material",
    "pvc material": "PVC Material",
    "structure":    "Structure",
    "mounting":     "Structure",
    "hardware":     "Structure",
}


# ── Row helpers (signatures unchanged) ───────────────────────────
def _is_product_row(row: list) -> bool:
    """In Supabase all fetched rows are product rows — just check non-empty."""
    if len(row) < 2:
        return False
    return bool(str(row[0]).strip() and str(row[1]).strip())


def _normalize(text: str) -> str:
    return str(text).strip().lower().replace(" ", "")


def _specs_match(row_spec: str, row_type: str,
                 query_spec: str, query_type: str) -> bool:
    """Fuzzy spec+type match (same logic as before)."""
    rs = _normalize(row_spec)
    rt = _normalize(row_type).replace("-", "")
    qs = _normalize(query_spec)
    qt = _normalize(query_type).replace("-", "")

    if not qs:          # user didn't specify spec → match any
        return True

    rs_num = rs.replace("w", "").replace("kw", "").replace("k", "")
    qs_num = qs.replace("w", "").replace("kw", "").replace("k", "")

    spec_match = (
        rs == qs or
        rs_num == qs_num or
        rs.startswith(qs) or
        qs.startswith(rs)
    )
    type_match = (
        rt == qt or
        rt.startswith(qt) or
        qt.startswith(rt) or
        qt == "" or rt == ""
    )
    return spec_match and type_match


# ── Core lookup ───────────────────────────────────────────────────
def find_product_row(brand: str, spec: str, type_: str, product_id: str = ""):
    """
    Returns (db_id, row_list) or (None, None).
    db_id is the Supabase primary key used for all UPDATE calls.
    """
    all_rows = _get_all_rows()

    # Fast path: direct product_id match
    if product_id:
        for row in all_rows:
            if row and row[0].strip() == product_id:
                return row[9], row     # row[9] = db id

    def _search(brand_q: str):
        bq = _normalize(brand_q)
        for row in all_rows:
            if not _is_product_row(row):
                continue
            rb = _normalize(row[1])
            if bq not in rb and rb not in bq:
                continue
            rs = str(row[2]).strip() if len(row) > 2 else ""
            rt = str(row[3]).strip() if len(row) > 3 else ""
            if _specs_match(rs, rt, spec, type_):
                return row[9], row
        return None, None

    db_id, row = _search(brand)
    if db_id:
        return db_id, row

    # Fallback: if brand contains acdb/dcdb, retry with just that keyword
    brand_lower = brand.lower()
    for kw in ["acdb", "dcdb"]:
        if kw in brand_lower and brand_lower != kw:
            db_id, row = _search(kw.upper())
            if db_id:
                return db_id, row

    # Fallback: spec contains acdb/dcdb
    spec_lower = spec.lower()
    for kw in ["acdb", "dcdb"]:
        if kw in spec_lower:
            db_id, row = _search(kw.upper())
            if db_id:
                return db_id, row

    return None, None


def get_all_products_by_brand(brand: str) -> list:
    """Return all products matching the given brand."""
    all_rows = _get_all_rows()
    bq = _normalize(brand)
    results = []
    for row in all_rows:
        if not _is_product_row(row):
            continue
        rb = _normalize(row[1])
        if bq in rb or rb in bq:
            qty = int(row[4]) if str(row[4]).isdigit() else 0
            results.append({
                "brand":    row[1].strip(),
                "spec":     row[2].strip(),
                "type":     row[3].strip(),
                "quantity": qty,
                "row_idx":  row[9],
                "score":    10
            })
    return results


def search_similar_products(brand: str, spec: str, type_: str, top_n: int = 4) -> list:
    """Fuzzy search — returns closest products when exact match fails."""
    all_rows = _get_all_rows()
    bq     = _normalize(brand)
    spec_q = _normalize(spec).replace("w", "").replace("kw", "")
    type_q = _normalize(type_).replace("-", "")

    scored = []
    for row in all_rows:
        if not _is_product_row(row):
            continue
        rb    = _normalize(row[1])
        rspec = _normalize(str(row[2])).replace("w", "").replace("kw", "")
        rtype = _normalize(str(row[3])).replace("-", "")

        acdb_fallback = any(kw in bq for kw in ["acdb", "dcdb"]) and (
            "acdb" in rb or "dcdb" in rb
        )
        if bq in rb or rb in bq or acdb_fallback:
            brand_score = 10
        else:
            continue

        spec_score = 0
        if spec_q and spec_q == rspec:                              spec_score = 3
        elif spec_q and (spec_q in rspec or rspec in spec_q):      spec_score = 2
        elif spec_q and len(spec_q) >= 2 and rspec.startswith(spec_q[:2]): spec_score = 1

        type_score = 1 if (not type_q or not rtype or type_q == rtype) else 0
        qty = int(row[4]) if str(row[4]).isdigit() else 0
        scored.append({
            "brand":    row[1].strip(),
            "spec":     row[2].strip(),
            "type":     row[3].strip(),
            "quantity": qty,
            "row_idx":  row[9],
            "score":    brand_score + spec_score + type_score
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_n]


# ── Stock read ────────────────────────────────────────────────────
def get_stock(brand: str, spec: str, type_: str, product_id: str = "") -> dict:
    db_id, row = find_product_row(brand, spec, type_, product_id)
    if db_id is None:
        return {"found": False, "brand": brand, "spec": spec, "type": type_}

    qty_raw = str(row[4]).strip() if len(row) > 4 else "0"
    qty     = int(qty_raw) if qty_raw.isdigit() else 0
    rate    = row[5].strip() if len(row) > 5 else "N/A"
    status  = row[7].strip() if len(row) > 7 else ""
    unit    = row[8].strip() if len(row) > 8 and isinstance(row[8], str) else "nos"

    return {
        "found":    True,
        "brand":    row[1].strip(),
        "spec":     row[2].strip(),
        "type":     row[3].strip(),
        "quantity": qty,
        "unit":     unit,
        "rate":     rate,
        "status":   status,
        "row_idx":  db_id,       # Supabase id — used by batch_deduct_all
    }


# ── Stock write helpers ───────────────────────────────────────────
def _status_for(qty: int) -> str:
    if qty == 0:   return "No Stock"
    if qty < 5:    return "Low Stock"
    return "In Stock"


def update_quantity(row_idx: int, new_qty: int):
    """Update quantity + status + total for a product (by Supabase id)."""
    status = _status_for(new_qty)
    try:
        client = _get_client()
        # Fetch current rate to recompute total
        resp = client.table("products").select("rate").eq("id", row_idx).single().execute()
        rate = float(resp.data.get("rate", 0) or 0)
        total = int(new_qty * rate) if rate > 0 else 0

        client.table("products").update({
            "quantity": new_qty,
            "status":   status,
            "total":    total,
        }).eq("id", row_idx).execute()
        _invalidate_rows_cache()
    except Exception as e:
        logger.error(f"update_quantity failed (id={row_idx}): {e}")


def update_rate(brand: str, spec: str, type_: str, rate: int) -> dict:
    info = get_stock(brand, spec, type_)
    if not info["found"]:
        return {"success": False, "error": f"Nahi mila: {brand} {spec} {type_}"}

    try:
        qty = info["quantity"]
        _get_client().table("products").update({
            "rate":  rate,
            "total": qty * rate if qty else 0,
        }).eq("id", info["row_idx"]).execute()
        _invalidate_rows_cache()
    except Exception as e:
        return {"success": False, "error": str(e)}

    return {
        "success":  True,
        "brand":    info["brand"],
        "spec":     info["spec"],
        "type":     info["type"],
        "rate":     rate,
        "quantity": info["quantity"],
    }


def add_stock(brand: str, spec: str, type_: str, quantity: int,
              operator: str, party: str = "", product_id: str = "") -> dict:
    info = get_stock(brand, spec, type_, product_id)
    if not info["found"]:
        return {"success": False, "error": f"Nahi mila: {brand} {spec} {type_}"}

    before = info["quantity"]
    after  = before + quantity
    update_quantity(info["row_idx"], after)

    _log_transaction(
        type_="ADD_IN",
        brand=info["brand"],
        spec=f"{info['spec']} {info['type']}",
        qty_change=quantity,
        before=before,
        after=after,
        vehicle_no="",
        operator=operator,
        party=party,
    )
    return {
        "success":  True,
        "brand":    info["brand"],
        "spec":     info["spec"],
        "type":     info["type"],
        "before":   before,
        "after":    after,
        "quantity": quantity,
        "unit":     info.get("unit", "nos"),
    }


def deduct_stock(brand: str, spec: str, type_: str, quantity: int,
                 vehicle_no: str, operator: str, party: str = "", product_id: str = "") -> dict:
    info = get_stock(brand, spec, type_, product_id)
    if not info["found"]:
        return {
            "success": False,
            "error":   f"Nahi mila: {brand} {spec} {type_}",
            "brand": brand, "spec": spec, "type": type_,
        }

    before = info["quantity"]
    if before < quantity:
        return {
            "success": False,
            "error":   f"Kam stock: {info['brand']} {info['spec']} — Hai {before}, chahiye {quantity}",
            "brand": info["brand"], "spec": info["spec"], "type": info["type"],
        }

    after = before - quantity
    update_quantity(info["row_idx"], after)

    _log_transaction(
        type_="SHIP_OUT",
        brand=info["brand"],
        spec=f"{info['spec']} {info['type']}",
        qty_change=-quantity,
        before=before,
        after=after,
        vehicle_no=vehicle_no,
        operator=operator,
        party=party,
    )
    return {
        "success":  True,
        "brand":    info["brand"],
        "spec":     info["spec"],
        "type":     info["type"],
        "before":   before,
        "after":    after,
        "quantity": quantity,
        "rate":     info["rate"],
        "unit":     info.get("unit", "nos"),
    }


def batch_deduct_all(pre_checked: list, vehicle_no: str, operator: str, party: str) -> tuple:
    """
    Deduct stock for ALL items. Each update is a single PK-based query —
    no rate limits, no batch-size cap (unlike Google Sheets).
    Returns (results, errors).
    """
    client  = _get_client()
    results = []
    errors  = []

    for item in pre_checked:
        db_id   = item["row_idx"]
        new_qty = item["before_qty"] - item["quantity"]
        status  = _status_for(new_qty)
        rate_raw = item.get("rate", "")
        try:
            rate  = float(str(rate_raw).replace(",", "").replace("₹", "").strip() or 0)
            total = int(new_qty * rate) if rate > 0 else 0
        except Exception:
            rate  = 0
            total = 0

        try:
            client.table("products").update({
                "quantity": new_qty,
                "status":   status,
                "total":    total,
            }).eq("id", db_id).execute()

            results.append({
                "success":  True,
                "brand":    item["brand"],
                "spec":     item["spec"],
                "type":     item["type"],
                "before":   item["before_qty"],
                "after":    new_qty,
                "quantity": item["quantity"],
                "rate":     rate_raw,
                "unit":     item.get("unit", "nos"),
            })
        except Exception as e:
            errors.append(f"Update failed for {item['brand']} {item['spec']}: {e}")

    _invalidate_rows_cache()

    # Log all successful transactions
    for item, result in zip(pre_checked, results):
        if result.get("success"):
            _log_transaction(
                type_="SHIP_OUT",
                brand=item["brand"],
                spec=f"{item['spec']} {item['type']}",
                qty_change=-item["quantity"],
                before=item["before_qty"],
                after=result["after"],
                vehicle_no=vehicle_no,
                operator=operator,
                party=party,
            )

    return results, errors


def add_new_product(category: str, brand: str, spec: str, type_: str,
                    operator: str, unit: str = "nos", init_qty: int = 0) -> dict:
    cat_key    = category.strip().lower()
    target_cat = CATEGORY_HEADERS.get(cat_key, category)

    CAT_CODES = {
        "solar panel": "SP",  "inverter": "INV",  "acdb": "ACDB",
        "dcdb":        "DCDB","acdb/dcdb":"ACDB",  "cable": "CAB",
        "pvc material":"PVC", "structure":"STR",
    }
    BRAND_CODES = {
        "waaree":"WAR","adani":"ADN","citizen":"CTZ","polycab":"PCB",
        "deye":"DEY","microtek":"MTK","eastman":"EST","havells":"HVL",
        "easyone":"EAS","waacab":"WCB",
    }
    cat_code   = CAT_CODES.get(cat_key, "GEN")
    brand_code = BRAND_CODES.get(brand.strip().lower(), "GEN")
    prefix     = f"{cat_code}-{brand_code}-"

    try:
        client = _get_client()

        # Auto-generate product_id: scan existing IDs with same prefix
        resp = client.table("products").select("product_id") \
                     .like("product_id", f"{prefix}%").execute()
        existing_nums = []
        for row in resp.data:
            pid = row.get("product_id", "")
            if pid.startswith(prefix):
                try:    existing_nums.append(int(pid.split("-")[-1]))
                except: pass
        product_id = f"{prefix}{max(existing_nums, default=0) + 1:03d}"

        # sort_order: place after last product in same category
        resp2 = client.table("products").select("sort_order") \
                      .eq("category", target_cat) \
                      .order("sort_order", desc=True).limit(1).execute()
        if resp2.data:
            sort_order = (resp2.data[0].get("sort_order") or 0) + 1
        else:
            resp3 = client.table("products").select("sort_order") \
                          .order("sort_order", desc=True).limit(1).execute()
            sort_order = (resp3.data[0].get("sort_order") or 0) + 1 if resp3.data else 1

        qty    = init_qty if init_qty > 0 else 0
        status = _status_for(qty)

        client.table("products").insert({
            "product_id": product_id,
            "brand":      brand,
            "spec":       spec,
            "type_":      type_,
            "quantity":   qty,
            "rate":       0,
            "total":      0,
            "status":     status,
            "unit":       unit,
            "category":   target_cat,
            "sort_order": sort_order,
        }).execute()

        # Invalidate both caches
        global _catalog_ts
        _catalog_ts = 0.0
        _invalidate_rows_cache()

        return {
            "success":    True,
            "brand":      brand,
            "spec":       spec,
            "type":       type_,
            "category":   target_cat,
            "unit":       unit,
            "row":        sort_order,
            "quantity":   qty,
            "product_id": product_id,
        }
    except Exception as e:
        logger.error(f"add_new_product failed: {e}")
        return {"success": False, "error": str(e)}


def get_full_stock() -> list:
    """Returns all products with section = category name."""
    try:
        resp = _get_client().table("products").select("*").order("sort_order").execute()
        results = []
        for p in resp.data:
            qty = int(p.get("quantity", 0) or 0)
            results.append({
                "section":  p.get("category", "General"),
                "brand":    str(p.get("brand", "") or ""),
                "spec":     str(p.get("spec",  "") or ""),
                "type":     str(p.get("type_", "") or ""),
                "quantity": qty,
                "unit":     str(p.get("unit",  "nos") or "nos"),
            })
        return results
    except Exception as e:
        logger.error(f"get_full_stock failed: {e}")
        return []


def get_party_summary(party_name: str) -> dict:
    """All transactions for a party (fuzzy name match)."""
    try:
        resp = _get_client().table("transactions").select("*") \
                            .order("timestamp").execute()
    except Exception as e:
        return {"error": str(e)}

    party_norm = _normalize(party_name)
    purchases  = []
    sales      = []

    for row in resp.data:
        rp = _normalize(str(row.get("party", "") or ""))
        if not rp or (party_norm not in rp and rp not in party_norm):
            continue
        try:
            qty = abs(int(row.get("qty_change", 0) or 0))
        except ValueError:
            qty = 0
        entry = {
            "timestamp": str(row.get("timestamp", ""))[:19],
            "type":      row.get("type_", ""),
            "brand":     str(row.get("brand", "")),
            "spec":      str(row.get("spec",  "")),
            "qty":       qty,
            "vehicle":   str(row.get("vehicle_no", "") or ""),
        }
        if row.get("type_") == "ADD_IN":
            purchases.append(entry)
        elif row.get("type_") == "SHIP_OUT":
            sales.append(entry)

    if not purchases and not sales:
        return {"found": False, "party": party_name}

    def _summarize(txns):
        totals = {}
        for t in txns:
            key = f"{t['brand']} {t['spec']}".strip()
            totals[key] = totals.get(key, 0) + t["qty"]
        return totals

    return {
        "found":      True,
        "party":      party_name,
        "purchases":  purchases,
        "sales":      sales,
        "buy_totals":  _summarize(purchases),
        "sell_totals": _summarize(sales),
    }


def _log_transaction(type_, brand, spec, qty_change, before, after,
                     vehicle_no, operator, party=""):
    """Silently log to transactions table. Never crashes main flow."""
    try:
        _get_client().table("transactions").insert({
            "timestamp":    datetime.now(IST).isoformat(),
            "type_":        type_,
            "brand":        brand,
            "spec":         spec,
            "qty_change":   qty_change,
            "stock_before": before,
            "stock_after":  after,
            "vehicle_no":   vehicle_no,
            "operator":     operator,
            "party":        party,
        }).execute()
    except Exception as e:
        logger.warning(f"Transaction log failed (non-critical): {e}")
