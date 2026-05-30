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
    "Vehicle No", "Operator"
]

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
    """Update Quantity (col 5) for a row. Col 7 = Total updated if rate exists."""
    ws = _get_sheet("Stock")
    ws.update_cell(row_idx, 5, new_qty)


def add_stock(brand: str, spec: str, type_: str, quantity: int, operator: str) -> dict:
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
        operator=operator
    )
    return {
        "success": True,
        "brand": info["brand"], "spec": info["spec"], "type": info["type"],
        "before": before, "after": after, "quantity": quantity
    }


def deduct_stock(brand: str, spec: str, type_: str, quantity: int,
                 vehicle_no: str, operator: str) -> dict:
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
        operator=operator
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
        return {"success": False, "error": "Sheet1 nahi mili"}

    all_rows = ws.get_all_values()
    valid_count = sum(1 for r in all_rows if _is_product_row(r))
    next_sr = valid_count + 1

    new_row = [next_sr, brand, spec, type_, 0, 0, 0, "⚪ No Stock"]
    ws.append_row(new_row)

    return {"success": True, "brand": brand, "spec": spec, "type": type_}


def _log_transaction(type_, brand, spec, qty_change, before, after, vehicle_no, operator):
    """Silently log to TRANSACTIONS sheet. Never crashes main flow."""
    try:
        ws = _get_or_create_transactions_sheet()
        from datetime import timezone, timedelta
        IST = timezone(timedelta(hours=5, minutes=30))
        ws.append_row([
            datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST"),
            type_, brand, spec,
            qty_change, before, after,
            vehicle_no, operator
        ])
    except Exception as e:
        logger.warning(f"Transaction log failed (non-critical): {e}")
