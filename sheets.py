import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# Col B values that indicate a category/section header row — skip these
HEADER_KEYWORDS = {
    "solar panel", "inverter", "acdb/dcdb", "cable", "cables", "dc cable",
    "ac cable", "ac cable 4sx2c", "earthing cable", "pvc material",
    "brand", "sr.no", "sr no", "category", "watt", "kw", "product",
    "meters", "pcs", "quantity", "stock status", "rate", "total"
}

# Col C spec values that indicate a header row — skip these
HEADER_SPEC_KEYWORDS = {
    "watt", "kw", "meter", "meters", "pcs", "spec", "quantity",
    "stock status", "rate", "total", "type"
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
    "pvc":         "PVC Material",
    "pvc material":"PVC Material",
    "structure":   "Structure",
    "mounting":    "Structure",
    "hardware":    "Structure",
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
    A product row has:
    - Column A (index 0): a digit (1, 2, 3...) — section/category headers use Roman numerals or letters
    - Column B (index 1): non-empty brand/product name that is not a known header keyword
    - Column C (index 2): non-empty spec value that is not a header keyword

    This approach works for ANY brand added directly to the sheet —
    no hardcoded brand list needed.
    """
    if len(row) < 3:
        return False

    col_a    = str(row[0]).strip()
    brand_raw = str(row[1]).strip()
    spec_raw  = str(row[2]).strip()

    # Col A must be a number to be a product row
    if not col_a.isdigit():
        return False

    if not brand_raw:
        return False

    brand_lower = brand_raw.lower().strip()
    spec_lower  = spec_raw.lower().strip()

    # Skip known category/section headers in brand column
    if brand_lower in HEADER_KEYWORDS:
        return False
    # Skip if spec column has a header keyword (but allow empty spec — cables/PVC have no spec)
    if spec_lower in HEADER_SPEC_KEYWORDS:
        return False

    return True


def _normalize(text: str) -> str:
    return str(text).strip().lower().replace(" ", "")


def _specs_match(row_spec: str, row_type: str, query_spec: str, query_type: str) -> bool:
    """
    Fuzzy match spec and type between sheet row and query.
    Handles: "575" vs "575w", "3kw" vs "3KW", "1P" vs "1p", "N-DCR" vs "n-dcr"
    If query_spec is empty, match any spec (user only specified the brand).
    """
    rs = _normalize(row_spec)
    rt = _normalize(row_type).replace("-", "")
    qs = _normalize(query_spec)
    qt = _normalize(query_type).replace("-", "")

    # Empty spec = user didn't specify → match any
    if not qs:
        return True

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


def get_all_products_by_brand(brand: str) -> list:
    """Return all products of a given brand from the sheet."""
    ws = _get_sheet("Stock")
    if not ws:
        return []
    all_rows = ws.get_all_values()
    brand_q = _normalize(brand)
    results = []
    for i, row in enumerate(all_rows):
        if not _is_product_row(row):
            continue
        row_brand = _normalize(row[1])
        if brand_q in row_brand or row_brand in brand_q:
            qty = int(row[4]) if len(row) > 4 and str(row[4]).isdigit() else 0
            results.append({
                "brand": row[1].strip(), "spec": row[2].strip(),
                "type": row[3].strip(), "quantity": qty, "row_idx": i + 1, "score": 10
            })
    return results


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
    rate   = row[5].strip() if len(row) > 5 else "N/A"
    status = row[7].strip() if len(row) > 7 else ""
    unit   = row[8].strip() if len(row) > 8 and row[8] else "nos"

    return {
        "found": True,
        "brand": row[1].strip(),
        "spec": row[2].strip(),
        "type": row[3].strip(),
        "quantity": qty,
        "unit": unit,
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
        "before": before, "after": after, "quantity": quantity,
        "unit": info.get("unit", "nos")
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
        "rate": info["rate"], "unit": info.get("unit", "nos")
    }


def add_new_product(category: str, brand: str, spec: str, type_: str, operator: str, unit: str = "nos", init_qty: int = 0) -> dict:
    ws = _get_sheet("Stock")
    if not ws:
        return {"success": False, "error": "Stock sheet nahi mili"}

    all_rows = ws.get_all_values()
    cat_key    = category.strip().lower()
    target_cat = CATEGORY_HEADERS.get(cat_key, category)
    brand_norm = _normalize(brand)

    # Scan for category section, then find last product row in it
    in_section  = False
    section_end = None   # 1-based row number of last product row in section
    brand_end   = None   # 1-based row number of last matching-brand row in section

    for i, row in enumerate(all_rows):
        cell_a = str(row[0]).strip()
        cell_b = str(row[1]).strip() if len(row) > 1 else ""
        combined = (cell_a + " " + cell_b).lower()

        # Detect start of our target category section
        if target_cat.lower() in combined and not cell_a.isdigit():
            in_section = True
            section_end = None
            brand_end   = None
            continue

        if not in_section:
            continue

        # Another section started — stop
        if not cell_a.isdigit() and any(
            h.lower() in combined
            for h in ["solar panel", "inverter", "acdb", "cable", "pvc material"]
        ) and combined.strip():
            # Only break if this is truly a new major section (roman numeral or letter header)
            if cell_a.upper() in ("I","II","III","IV","V","VI","A","B","C","D","E") or \
               any(x in combined for x in ["solar panel","inverter","acdb/dcdb","iv. cable","v. pvc"]):
                break

        if _is_product_row(row):
            section_end = i + 1   # 1-based
            if brand_norm in _normalize(cell_b) or _normalize(cell_b) in brand_norm:
                brand_end = i + 1

    # Target row = after brand group or after section
    base_row = brand_end if brand_end is not None else section_end
    if base_row is not None:
        # Find first truly empty row at or after base_row + 1
        target_row = base_row + 1
        while target_row <= len(all_rows):
            r = all_rows[target_row - 1]
            if not any(str(c).strip() for c in r[:9]):
                break
            target_row += 1
    else:
        # No section found — append after last non-empty row
        target_row = len(all_rows) + 1
        for i in range(len(all_rows) - 1, -1, -1):
            if any(str(c).strip() for c in all_rows[i][:9]):
                target_row = i + 2
                break

    # Count existing product rows in section to assign Sr.No
    sr_no = 1
    if section_end is not None:
        in_sec = False
        for row in all_rows:
            combined = (str(row[0]) + " " + (str(row[1]) if len(row) > 1 else "")).lower()
            if target_cat.lower() in combined and not str(row[0]).strip().isdigit():
                in_sec = True
                sr_no  = 1
                continue
            if in_sec and _is_product_row(row):
                sr_no += 1

    qty    = init_qty if init_qty > 0 else 0
    status = "In Stock" if qty > 0 else "No Stock"
    new_row = [sr_no, brand, spec, type_, qty, "", "", status, unit]
    ws.update(f"A{target_row}:I{target_row}", [new_row])

    # Copy formatting from the nearest PRODUCT row above (skip headers)
    try:
        from config import GOOGLE_SHEET_ID
        spreadsheet = _client().open_by_key(GOOGLE_SHEET_ID)
        sheet_id = ws.id

        # Find nearest product row above target (col A is a digit)
        copy_from = None
        for i in range(target_row - 2, -1, -1):
            if i < len(all_rows) and str(all_rows[i][0]).strip().isdigit():
                copy_from = i + 1  # 1-based
                break

        if copy_from:
            spreadsheet.batch_update({"requests": [{
                "copyPaste": {
                    "source": {
                        "sheetId": sheet_id,
                        "startRowIndex": copy_from - 1,
                        "endRowIndex": copy_from,
                        "startColumnIndex": 0,
                        "endColumnIndex": 9
                    },
                    "destination": {
                        "sheetId": sheet_id,
                        "startRowIndex": target_row - 1,
                        "endRowIndex": target_row,
                        "startColumnIndex": 0,
                        "endColumnIndex": 9
                    },
                    "pasteType": "PASTE_FORMAT"
                }
            }]})
            # Re-write data after format copy
            ws.update(f"A{target_row}:I{target_row}", [new_row])
    except Exception as e:
        logger.warning(f"Format copy failed (non-critical): {e}")

    return {"success": True, "brand": brand, "spec": spec, "type": type_,
            "category": target_cat, "unit": unit, "row": target_row, "quantity": qty}


def get_full_stock() -> list:
    """
    Returns all product rows grouped by section.
    Each entry: {section, brand, spec, type, quantity, unit, status}
    """
    ws = _get_sheet("Stock")
    if not ws:
        return []

    all_rows = ws.get_all_values()
    current_section = "General"
    results = []

    for row in all_rows:
        col_a = str(row[0]).strip()
        col_b = str(row[1]).strip() if len(row) > 1 else ""
        combined = (col_a + " " + col_b).lower()

        # Detect section header (non-digit col A with meaningful content)
        if not col_a.isdigit() and col_b:
            for sec in ["Solar Panel", "Inverter", "ACDB/DCDB", "Cable", "PVC Material", "Structure"]:
                if sec.lower() in combined:
                    current_section = sec
                    break
            continue

        if not _is_product_row(row):
            continue

        qty_raw = str(row[4]).strip() if len(row) > 4 else "0"
        qty = int(qty_raw) if qty_raw.isdigit() else 0
        unit = str(row[8]).strip() if len(row) > 8 and row[8] else "nos"

        results.append({
            "section":  current_section,
            "brand":    col_b,
            "spec":     str(row[2]).strip() if len(row) > 2 else "",
            "type":     str(row[3]).strip() if len(row) > 3 else "",
            "quantity": qty,
            "unit":     unit,
        })

    return results


def get_party_summary(party_name: str) -> dict:
    """
    Returns all transactions for a party (fuzzy name match).
    Summarizes: total purchased (ADD_IN), total sold (SHIP_OUT), product-wise breakdown.
    """
    try:
        ws = _get_or_create_transactions_sheet()
        rows = ws.get_all_values()
    except Exception as e:
        return {"error": str(e)}

    if len(rows) < 2:
        return {"found": False, "party": party_name}

    headers = rows[0]
    party_norm = _normalize(party_name)

    purchases = []   # ADD_IN rows matching party
    sales     = []   # SHIP_OUT rows matching party

    for row in rows[1:]:
        if len(row) < 10:
            continue
        row_party = _normalize(str(row[9]))   # col J = Party
        if not row_party or party_norm not in row_party and row_party not in party_norm:
            continue
        try:
            qty = int(str(row[4]).replace("-", "").strip() or 0)
        except ValueError:
            qty = 0
        entry = {
            "timestamp": row[0],
            "type":      row[1],
            "brand":     row[2],
            "spec":      row[3],
            "qty":       qty,
            "vehicle":   row[7],
        }
        if row[1] == "ADD_IN":
            purchases.append(entry)
        elif row[1] == "SHIP_OUT":
            sales.append(entry)

    if not purchases and not sales:
        return {"found": False, "party": party_name}

    # Product-wise summary
    def summarize(txns):
        totals = {}
        for t in txns:
            key = f"{t['brand']} {t['spec']}"
            totals[key] = totals.get(key, 0) + t["qty"]
        return totals

    return {
        "found":     True,
        "party":     party_name,
        "purchases": purchases,
        "sales":     sales,
        "buy_totals":  summarize(purchases),
        "sell_totals": summarize(sales),
    }


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
