import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# Rows where Brand column contains these strings are category headers — skip them
HEADER_KEYWORDS = {
    "solar panel", "inverter", "acdb/dcdb", "acdb", "dcdb", "cable", "cables",
    "brand", "sr.no", "sr no", "category", "watt", "kw", "product"
}

# Valid product brands (lowercase)
VALID_BRANDS = {
    "waaree", "adani", "citizen", "polycab", "deye", "microtek", "eastman",
    "acdb", "dcdb", "havells"
}


def _client():
    from config import GOOGLE_CREDENTIALS
    creds = Credentials.from_service_account_info(GOOGLE_CREDENTIALS, scopes=SCOPES)
    return gspread.authorize(creds)


def _get_sheet(sheet_name="Stock"):
    from config import GOOGLE_SHEET_ID
    spreadsheet = _client().open_by_key(GOOGLE_SHEET_ID)
    try:
        return spreadsheet.worksheet(sheet_name)
    except gspread.WorksheetNotFound:
        return None


TRANSACTION_HEADERS = [
    "Timestamp", "Type", "Brand", "Spec",
    "Qty Change", "Stock Before", "Stock After",
    "Vehicle No", "Operator", "Party"
]

# Maps category keywords → header text in sheet
CATEGORY_HEADERS = {
    "solar panel": "Solar Panel",
    "solar":       "Solar Panel",
    "panel":       "Solar Panel",
    "inverter":    "Inverter",
    "acdb":        "ACDB/DCDB",
    "dcdb":        "ACDB/DCDB",
    "acdb/dcdb":   "ACDB/DCDB",
    "cable":       "Cable",
    "cables":      "Cable",
    "wire":        "Cable",
}

def _get_or_create_transactions_sheet():
    from config import GOOGLE_SHEET_ID
    spreadsheet = _client().open_by_key(GOOGLE_SHEET_ID)
    try:
        ws = spreadsheet.worksheet("Transacation")
        if ws.row_values(1) != TRANSACTION_HEADERS:
            ws.update("A1", [TRANSACTION_HEADERS])
        return ws
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title="Transacation", rows=1000, cols=9)
        ws.append_row(TRANSACTION_HEADERS)
        return ws


def _is_product_row(row: list) -> bool:
    """
    Sheet columns: Sr.no | Brand | Watt | DCR/N-DCR | Quantity | Rate | Total | Stock Status
    A valid product row:
    - Column B (index 1): a known brand name
    - Column C (index 2): a non-empty spec value
    """
    if len(row) < 3:
        return False
    brand_raw = str(row[1]).strip()
    spec_raw = str(row[2]).strip()
    brand_lower = brand_raw.lower().replace(".", "").replace(" ", "")

    if not brand_raw or not spec_raw:
        return False
    if brand_lower in HEADER_KEYWORDS:
        return False
    if spec_raw.lower() in ("watt", "kw", "meter", "spec", ""):
        return False
    # Brand must be a known brand
    for valid in VALID_BRANDS:
        if valid in brand_lower:
            return True
    return False


def _normalize(text: str) -> str:
    return str(text).strip().lower().replace(" ", "")


def _specs_match(row_spec: str, row_type: str, query_spec: str, query_type: str) -> bool:
    """
    Fuzzy match spec and type between sheet row and query.
    Handles: "575" vs "575w", "3kw" vs "3KW", "1P" vs "1p", "N-DCR" vs "n-dcr"
    """
    rs = _normalize(row_spec)
    rt = _normalize(row_type).replace("-", "")
    qs = _normalize(query_spec)
    qt = _normalize(query_type).replace("-", "")

    # Strip units for numeric comparison
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


def find_product_row(brand: str, spec: str, type_: str):
    """
    Find a product row in Sheet1.
    Returns (row_index_1based, row_data) or (None, None)
    """
    ws = _get_sheet("Stock")
    if not ws:
        return None, None

    all_rows = ws.get_all_values()
    brand_norm = _normalize(brand)

    for i, row in enumerate(all_rows):
        if not _is_product_row(row):
            continue
        row_brand = _normalize(row[1])
        # Allow partial match: "waaree" matches "waaree solar" etc
        if brand_norm not in row_brand and row_brand not in brand_norm:
            continue
        row_spec = str(row[2]).strip() if len(row) > 2 else ""
        row_type = str(row[3]).strip() if len(row) > 3 else ""
        if _specs_match(row_spec, row_type, spec, type_):
            return i + 1, row  # 1-based index

    return None, None


def search_similar_products(brand: str, spec: str, type_: str, top_n: int = 4) -> list:
    """
    Fuzzy search — returns top_n closest products when exact match fails.
    Brand match is dominant — if brand matches, only brand-matching rows are returned.
    """
    ws = _get_sheet("Stock")
    if not ws:
        return []

    all_rows = ws.get_all_values()
    brand_q = _normalize(brand)
    spec_q  = _normalize(spec).replace("w", "").replace("kw", "")
    type_q  = _normalize(type_).replace("-", "")

    scored = []
    for i, row in enumerate(all_rows):
        if not _is_product_row(row):
            continue
        row_brand = _normalize(row[1])
        row_spec  = _normalize(str(row[2])).replace("w", "").replace("kw", "")
        row_type  = _normalize(str(row[3])).replace("-", "")

        # Brand score — DOMINANT: if brand doesn't match at all, skip row
        if brand_q in row_brand or row_brand in brand_q:
            brand_score = 10
        else:
            continue   # Wrong brand → never suggest

        # Spec match scoring
        spec_score = 0
        if spec_q and spec_q == row_spec:
            spec_score = 3
        elif spec_q and (spec_q in row_spec or row_spec in spec_q):
            spec_score = 2
        elif spec_q and len(spec_q) >= 2 and row_spec.startswith(spec_q[:2]):
            spec_score = 1

        # Type match scoring
        type_score = 1 if (not type_q or not row_type or type_q == row_type) else 0

        score = brand_score + spec_score + type_score
        qty = int(row[4]) if len(row) > 4 and str(row[4]).isdigit() else 0
        scored.append({
            "brand":    row[1].strip(),
            "spec":     row[2].strip(),
            "type":     row[3].strip(),
            "quantity": qty,
            "row_idx":  i + 1,
            "score":    score
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_n]


def get_stock(brand: str, spec: str, type_: str) -> dict:
    row_idx, row = find_product_row(brand, spec, type_)
    if row_idx is None:
        return {"found": False, "brand": brand, "spec": spec, "type": type_}

    qty_raw = str(row[4]).strip() if len(row) > 4 else "0"
    qty = int(qty_raw) if qty_raw.isdigit() else 0
    rate = row[5].strip() if len(row) > 5 else "N/A"
    status = row[7].strip() if len(row) > 7 else ""

    return {
        "found": True,
        "brand": row[1].strip(),
        "spec": row[2].strip(),
        "type": row[3].strip(),
        "quantity": qty,
        "rate": rate,
        "status": status,
        "row_idx": row_idx
    }


def update_quantity(row_idx: int, new_qty: int):
    ws = _get_sheet("Stock")
    ws.update_cell(row_idx, 5, new_qty)
    # Recalculate Total = Qty × Rate in col G (7)
    row = ws.row_values(row_idx)
    rate_raw = row[5].strip() if len(row) > 5 else ""
    try:
        rate = float(str(rate_raw).replace(",", "").replace("₹", "").strip() or 0)
        if rate > 0:
            ws.update_cell(row_idx, 7, int(new_qty * rate))
    except Exception:
        pass


def update_rate(brand: str, spec: str, type_: str, rate: int) -> dict:
    info = get_stock(brand, spec, type_)
    if not info["found"]:
        return {"success": False, "error": f"Nahi mila: {brand} {spec} {type_}"}

    ws = _get_sheet("Stock")
    row_idx = info["row_idx"]
    qty = info["quantity"]
    ws.update_cell(row_idx, 6, rate)                         # col F = Rate
    ws.update_cell(row_idx, 7, qty * rate if qty else 0)     # col G = Total
    return {
        "success": True,
        "brand": info["brand"], "spec": info["spec"], "type": info["type"],
        "rate": rate, "quantity": qty
    }


def add_stock(brand: str, spec: str, type_: str, quantity: int, operator: str, party: str = "") -> dict:
    info = get_stock(brand, spec, type_)
    if not info["found"]:
        return {"success": False, "error": f"Nahi mila: {brand} {spec} {type_}"}

    before = info["quantity"]
    after = before + quantity
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
        party=party
    )
    return {
        "success": True,
        "brand": info["brand"], "spec": info["spec"], "type": info["type"],
        "before": before, "after": after, "quantity": quantity
    }


def deduct_stock(brand: str, spec: str, type_: str, quantity: int,
                 vehicle_no: str, operator: str, party: str = "") -> dict:
    info = get_stock(brand, spec, type_)
    if not info["found"]:
        return {
            "success": False,
            "error": f"Nahi mila: {brand} {spec} {type_}",
            "brand": brand, "spec": spec, "type": type_
        }

    before = info["quantity"]
    if before < quantity:
        return {
            "success": False,
            "error": f"Kam stock: {info['brand']} {info['spec']} — Hai {before}, chahiye {quantity}",
            "brand": info["brand"], "spec": info["spec"], "type": info["type"]
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
        party=party
    )
    return {
        "success": True,
        "brand": info["brand"], "spec": info["spec"], "type": info["type"],
        "before": before, "after": after, "quantity": quantity,
        "rate": info["rate"]
    }


def add_new_product(category: str, brand: str, spec: str, type_: str, operator: str) -> dict:
    ws = _get_sheet("Stock")
    if not ws:
        return {"success": False, "error": "Stock sheet nahi mili"}

    all_rows = ws.get_all_values()

    # Resolve category header text
    cat_key = category.strip().lower()
    target_cat = CATEGORY_HEADERS.get(cat_key, "")

    # Find insert position:
    # 1. Find the category section header row
    # 2. Within it, find last row of same brand → insert after it
    # 3. If brand not found in section → insert after last product row of section
    # 4. If category not found at all → append at end

    cat_start = None       # 0-based index of category header row
    brand_last = None      # 0-based index of last row of same brand in section
    section_last = None    # 0-based index of last product row in section

    brand_norm = _normalize(brand)

    for i, row in enumerate(all_rows):
        cell_b = str(row[1]).strip().lower() if len(row) > 1 else ""
        cell_a = str(row[0]).strip().lower() if len(row) > 0 else ""

        # Detect category header row (merged or col B contains category name)
        if target_cat and target_cat.lower() in (cell_b + " " + cell_a):
            cat_start = i
            brand_last = None   # reset when new section found
            section_last = None
            continue

        if cat_start is not None:
            # If we hit another category header, section ended
            if any(h.lower() in cell_b for h in CATEGORY_HEADERS.values()) and i != cat_start:
                break
            if _is_product_row(row):
                section_last = i
                if brand_norm in _normalize(str(row[1])) or _normalize(str(row[1])) in brand_norm:
                    brand_last = i

    valid_count = sum(1 for r in all_rows if _is_product_row(r))
    next_sr = valid_count + 1
    new_row = ["", brand, spec, type_, 0, "", "", "⚪ No Stock"]

    if brand_last is not None:
        insert_idx = brand_last + 2   # +1 for 1-based, +1 to insert after
        ws.insert_row(new_row, insert_idx)
    elif section_last is not None:
        insert_idx = section_last + 2
        ws.insert_row(new_row, insert_idx)
    else:
        ws.append_row(new_row)

    return {"success": True, "brand": brand, "spec": spec, "type": type_, "category": target_cat or category}


def _log_transaction(type_, brand, spec, qty_change, before, after, vehicle_no, operator, party=""):
    """Silently log to TRANSACTIONS sheet. Never crashes main flow."""
    try:
        ws = _get_or_create_transactions_sheet()
        from datetime import timezone, timedelta
        IST = timezone(timedelta(hours=5, minutes=30))
        ws.append_row([
            datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST"),
            type_, brand, spec,
            qty_change, before, after,
            vehicle_no, operator, party
        ])
    except Exception as e:
        logger.warning(f"Transaction log failed (non-critical): {e}")
