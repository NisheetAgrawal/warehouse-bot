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
        # Row 1 now has product_id in col A; actual headers start at col B
        current_headers = ws.row_values(1)
        # If col B onwards don't match expected headers, rewrite (but keep product_id in A)
        if current_headers[1:len(TRANSACTION_HEADERS)+1] != TRANSACTION_HEADERS:
            ws.update("B1", [TRANSACTION_HEADERS])
        return ws
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title="Transacation", rows=1000, cols=11)
        ws.update("A1", [["product_id"] + TRANSACTION_HEADERS])
        return ws


def _is_product_row(row: list) -> bool:
    """
    Sheet now has product_id as col A (index 0).
    A product row has:
    - Col B (index 1): Sr.No — must be a digit (1, 2, 3...)
    - Col C (index 2): non-empty brand/product name, not a known header keyword
    - Col D (index 3): spec value (may be empty for cables/PVC)
    """
    if len(row) < 3:
        return False

    col_b     = str(row[1]).strip()   # Sr.No
    brand_raw = str(row[2]).strip()   # Brand
    spec_raw  = str(row[3]).strip() if len(row) > 3 else ""  # Spec

    # Sr.No must be a number
    if not col_b.isdigit():
        return False

    if not brand_raw:
        return False

    brand_lower = brand_raw.lower().strip()
    spec_lower  = spec_raw.lower().strip()

    if brand_lower in HEADER_KEYWORDS:
        return False
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

    Smart fallback: if brand contains 'acdb' or 'dcdb' mixed with a manufacturer
    name (e.g. 'Polycab ACDB'), also tries searching with just 'ACDB'/'DCDB'.
    """
    ws = _get_sheet("Stock")
    if not ws:
        return None, None

    all_rows = ws.get_all_values()

    def _search(brand_q):
        brand_q_norm = _normalize(brand_q)
        for i, row in enumerate(all_rows):
            if not _is_product_row(row):
                continue
            row_brand = _normalize(row[2])        # col C = Brand
            if brand_q_norm not in row_brand and row_brand not in brand_q_norm:
                continue
            row_spec = str(row[3]).strip() if len(row) > 3 else ""   # col D
            row_type = str(row[4]).strip() if len(row) > 4 else ""   # col E
            if _specs_match(row_spec, row_type, spec, type_):
                return i + 1, row
        return None, None

    # Primary search
    row_idx, row = _search(brand)
    if row_idx:
        return row_idx, row

    # Fallback: if brand has both a manufacturer AND "acdb"/"dcdb",
    # retry with just the product type (e.g. "Polycab ACDB" → "ACDB")
    brand_lower = brand.lower()
    for keyword in ["acdb", "dcdb"]:
        if keyword in brand_lower and brand_lower != keyword:
            row_idx, row = _search(keyword.upper())
            if row_idx:
                return row_idx, row

    # Fallback: if brand is a manufacturer name (Polycab/Waaree etc.) but
    # spec contains "acdb" or "dcdb", try brand="ACDB"/"DCDB" with remaining spec
    spec_lower = spec.lower()
    for keyword in ["acdb", "dcdb"]:
        if keyword in spec_lower:
            clean_spec = spec_lower.replace(keyword, "").strip()
            row_idx, row = _search(keyword.upper())
            if row_idx:
                return row_idx, row

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
        row_brand = _normalize(row[2])            # col C = Brand
        if brand_q in row_brand or row_brand in brand_q:
            qty = int(row[5]) if len(row) > 5 and str(row[5]).isdigit() else 0
            results.append({
                "brand": row[2].strip(), "spec": row[3].strip(),
                "type": row[4].strip(), "quantity": qty, "row_idx": i + 1, "score": 10
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
        row_brand = _normalize(row[2])            # col C = Brand
        row_spec  = _normalize(str(row[3])).replace("w", "").replace("kw", "")  # col D
        row_type  = _normalize(str(row[4])).replace("-", "")                     # col E

        acdb_fallback = any(kw in brand_q for kw in ["acdb", "dcdb"]) and (
            "acdb" in row_brand or "dcdb" in row_brand
        )
        if brand_q in row_brand or row_brand in brand_q or acdb_fallback:
            brand_score = 10
        else:
            continue

        spec_score = 0
        if spec_q and spec_q == row_spec:
            spec_score = 3
        elif spec_q and (spec_q in row_spec or row_spec in spec_q):
            spec_score = 2
        elif spec_q and len(spec_q) >= 2 and row_spec.startswith(spec_q[:2]):
            spec_score = 1

        type_score = 1 if (not type_q or not row_type or type_q == row_type) else 0

        score = brand_score + spec_score + type_score
        qty = int(row[5]) if len(row) > 5 and str(row[5]).isdigit() else 0  # col F
        scored.append({
            "brand":    row[2].strip(),
            "spec":     row[3].strip(),
            "type":     row[4].strip(),
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

    qty_raw = str(row[5]).strip() if len(row) > 5 else "0"   # col F = Quantity
    qty = int(qty_raw) if qty_raw.isdigit() else 0
    rate   = row[6].strip() if len(row) > 6 else "N/A"       # col G = Rate
    status = row[8].strip() if len(row) > 8 else ""           # col I = Stock Status
    unit   = row[9].strip() if len(row) > 9 and row[9] else "nos"  # col J = Unit

    return {
        "found": True,
        "brand": row[2].strip(),   # col C
        "spec":  row[3].strip(),   # col D
        "type":  row[4].strip(),   # col E
        "quantity": qty,
        "unit": unit,
        "rate": rate,
        "status": status,
        "row_idx": row_idx
    }


def update_quantity(row_idx: int, new_qty: int):
    """Update qty + status in ONE batch call to avoid partial-update failures."""
    ws = _get_sheet("Stock")
    if new_qty == 0:
        status = "No Stock"
    elif new_qty < 5:
        status = "Low Stock"
    else:
        status = "In Stock"
    try:
        # Col F=qty, Col G=rate, Col H=total, Col I=status  (product_id now in col A)
        row = ws.row_values(row_idx)
        rate_raw = row[6].strip() if len(row) > 6 else ""    # col G = Rate
        try:
            rate = float(str(rate_raw).replace(",", "").replace("₹", "").strip() or 0)
            total = int(new_qty * rate) if rate > 0 else ""
        except Exception:
            total = ""
        updates = [{"range": f"F{row_idx}", "values": [[new_qty]]},   # col F = Qty
                   {"range": f"I{row_idx}", "values": [[status]]}]    # col I = Status
        if total != "":
            updates.append({"range": f"H{row_idx}", "values": [[total]]})  # col H = Total
        ws.batch_update(updates)
    except Exception as e:
        logger.warning(f"batch update failed, trying single cell: {e}")
        try:
            ws.update_cell(row_idx, 6, new_qty)   # col F (1-indexed = 6)
        except Exception as e2:
            logger.error(f"update_quantity failed completely: {e2}")


def update_rate(brand: str, spec: str, type_: str, rate: int) -> dict:
    info = get_stock(brand, spec, type_)
    if not info["found"]:
        return {"success": False, "error": f"Nahi mila: {brand} {spec} {type_}"}

    ws = _get_sheet("Stock")
    row_idx = info["row_idx"]
    qty = info["quantity"]
    ws.update_cell(row_idx, 7, rate)                          # col G = Rate  (shifted +1)
    ws.update_cell(row_idx, 8, qty * rate if qty else 0)     # col H = Total (shifted +1)
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
        # With product_id in col A: col B (index 1) = Sr.No, col C (index 2) = Brand
        cell_b = str(row[1]).strip() if len(row) > 1 else ""   # Sr.No / section header text
        cell_c = str(row[2]).strip() if len(row) > 2 else ""   # Brand
        combined = (cell_b + " " + cell_c).lower()

        # Detect start of our target category section
        if target_cat.lower() in combined and not cell_b.isdigit():
            in_section = True
            section_end = None
            brand_end   = None
            continue

        if not in_section:
            continue

        # Another section started — stop
        if not cell_b.isdigit() and any(
            h.lower() in combined
            for h in ["solar panel", "inverter", "acdb", "cable", "pvc material"]
        ) and combined.strip():
            if cell_b.upper() in ("I","II","III","IV","V","VI","A","B","C","D","E") or \
               any(x in combined for x in ["solar panel","inverter","acdb/dcdb","iv. cable","v. pvc"]):
                break

        if _is_product_row(row):
            section_end = i + 1   # 1-based
            if brand_norm in _normalize(cell_c) or _normalize(cell_c) in brand_norm:
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
            col_b = str(row[1]).strip() if len(row) > 1 else ""
            col_c = str(row[2]).strip() if len(row) > 2 else ""
            combined = (col_b + " " + col_c).lower()
            if target_cat.lower() in combined and not col_b.isdigit():
                in_sec = True
                sr_no  = 1
                continue
            if in_sec and _is_product_row(row):
                sr_no += 1

    qty    = init_qty if init_qty > 0 else 0
    if qty == 0:
        status = "No Stock"
    elif qty < 5:
        status = "Low Stock"
    else:
        status = "In Stock"
    # Write to cols B:J (leave col A = product_id blank; assigned manually or later)
    new_row = [sr_no, brand, spec, type_, qty, "", "", status, unit]
    ws.update(f"B{target_row}:J{target_row}", [new_row])

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
                        "startColumnIndex": 1,    # col B onwards (skip product_id col)
                        "endColumnIndex": 10      # cols B-J (9 data cols)
                    },
                    "destination": {
                        "sheetId": sheet_id,
                        "startRowIndex": target_row - 1,
                        "endRowIndex": target_row,
                        "startColumnIndex": 1,
                        "endColumnIndex": 10
                    },
                    "pasteType": "PASTE_FORMAT"
                }
            }]})
            # Re-write data after format copy
            ws.update(f"B{target_row}:J{target_row}", [new_row])
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
        # col A (index 0) = product_id, col B (index 1) = Sr.No/header, col C (index 2) = Brand
        col_b = str(row[1]).strip() if len(row) > 1 else ""   # Sr.No or section header text
        col_c = str(row[2]).strip() if len(row) > 2 else ""   # Brand
        combined = (col_b + " " + col_c).lower()

        # Detect section header: col B is non-digit with section keyword
        if not col_b.isdigit() and col_b:
            for sec in ["Solar Panel", "Inverter", "ACDB/DCDB", "Cable", "PVC Material", "Structure"]:
                if sec.lower() in combined:
                    current_section = sec
                    break
            continue

        if not _is_product_row(row):
            continue

        qty_raw = str(row[5]).strip() if len(row) > 5 else "0"   # col F = Qty
        qty = int(qty_raw) if qty_raw.isdigit() else 0
        unit = str(row[9]).strip() if len(row) > 9 and row[9] else "nos"  # col J = Unit

        results.append({
            "section":  current_section,
            "brand":    col_c,
            "spec":     str(row[3]).strip() if len(row) > 3 else "",   # col D
            "type":     str(row[4]).strip() if len(row) > 4 else "",   # col E
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
        if len(row) < 11:
            continue
        # product_id now in col A (index 0); data cols shifted +1
        row_party = _normalize(str(row[10]))  # col K = Party
        if not row_party or party_norm not in row_party and row_party not in party_norm:
            continue
        try:
            qty = int(str(row[5]).replace("-", "").strip() or 0)   # col F = Qty Change
        except ValueError:
            qty = 0
        entry = {
            "timestamp": row[1],   # col B
            "type":      row[2],   # col C
            "brand":     row[3],   # col D
            "spec":      row[4],   # col E
            "qty":       qty,
            "vehicle":   row[8],   # col I
        }
        if row[2] == "ADD_IN":
            purchases.append(entry)
        elif row[2] == "SHIP_OUT":
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
        # Col A = product_id (blank for now), then transaction data from col B onwards
        ws.append_row([
            "",   # product_id — blank; to be matched separately
            datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST"),
            type_, brand, spec,
            qty_change, before, after,
            vehicle_no, operator, party
        ])
    except Exception as e:
        logger.warning(f"Transaction log failed (non-critical): {e}")
