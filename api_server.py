"""
api_server.py — REST API for the Swadev Energies Warehouse frontend.
Run: uvicorn api_server:app --reload --port 8000

Run this SQL in Supabase SQL Editor once before starting:
──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS categories (
  id           SERIAL PRIMARY KEY,
  name         TEXT UNIQUE NOT NULL,
  code         TEXT DEFAULT '',
  default_unit TEXT DEFAULT 'nos',
  created_at   TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS brands (
  id         SERIAL PRIMARY KEY,
  name       TEXT UNIQUE NOT NULL,
  code       TEXT DEFAULT '',
  created_at TIMESTAMPTZ DEFAULT NOW()
);
-- Seed from existing data
INSERT INTO categories (name, code, default_unit) VALUES
  ('Solar Panel','SP','nos'),('Inverter','INV','nos'),
  ('ACDB/DCDB','ACDB','nos'),('Cable','CAB','meters'),
  ('PVC Material','PVC','pcs'),('Structure','STR','pcs')
ON CONFLICT (name) DO NOTHING;
INSERT INTO brands (name, code) VALUES
  ('Waaree','WAR'),('Adani','ADN'),('Citizen','CTZ'),('Polycab','PCB'),
  ('Deye','DEY'),('Microtek','MTK'),('Eastman','EST'),('Havells','HVL'),
  ('Easyone','EAS'),('Waacab','WCB')
ON CONFLICT (name) DO NOTHING;
──────────────────────────────────────────────────────────────────
"""

import os, sys, json
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.dirname(__file__))

from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from typing import List, Optional
from supabase import create_client

app = FastAPI(title="Swadev Warehouse API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

IST = timezone(timedelta(hours=5, minutes=30))


def _sb():
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])


def _status(qty: int) -> str:
    if qty == 0:  return "No Stock"
    if qty < 5:   return "Low Stock"
    return "In Stock"


# ── GET /api/products ─────────────────────────────────────────────
@app.get("/api/products")
def get_products():
    resp = _sb().table("products").select("*").order("sort_order").execute()
    return resp.data


# ── GET /api/products/stats ───────────────────────────────────────
@app.get("/api/products/stats")
def get_stats():
    resp = _sb().table("products").select("quantity").execute()
    products = resp.data
    return {
        "in_stock":  sum(1 for p in products if (p.get("quantity") or 0) >= 5),
        "low_stock": sum(1 for p in products if 0 < (p.get("quantity") or 0) < 5),
        "out_stock": sum(1 for p in products if (p.get("quantity") or 0) == 0),
        "total":     len(products),
    }


# ── GET /api/transactions ─────────────────────────────────────────
@app.get("/api/transactions")
def get_transactions():
    resp = _sb().table("transactions").select("*") \
                .order("timestamp", desc=True).limit(100).execute()
    return resp.data


# ── GET /api/categories ───────────────────────────────────────────
@app.get("/api/categories")
def get_categories():
    resp = _sb().table("categories").select("*").order("name").execute()
    return resp.data


# ── POST /api/categories ──────────────────────────────────────────
class CategoryPayload(BaseModel):
    name:         str
    code:         Optional[str] = ""
    default_unit: Optional[str] = "nos"

@app.post("/api/categories")
def create_category(payload: CategoryPayload):
    sb = _sb()
    # Derive code from name if not provided
    code = payload.code or "".join(w[0].upper() for w in payload.name.split()[:3])
    try:
        resp = sb.table("categories").insert({
            "name": payload.name.strip(),
            "code": code,
            "default_unit": payload.default_unit,
        }).execute()
        return resp.data[0] if resp.data else {"name": payload.name, "code": code}
    except Exception as e:
        # If duplicate, fetch existing
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            existing = sb.table("categories").select("*").eq("name", payload.name).single().execute()
            return existing.data
        raise HTTPException(status_code=400, detail=str(e))


# ── GET /api/brands ───────────────────────────────────────────────
@app.get("/api/brands")
def get_brands():
    resp = _sb().table("brands").select("*").order("name").execute()
    return resp.data


# ── POST /api/brands ──────────────────────────────────────────────
class BrandPayload(BaseModel):
    name: str
    code: Optional[str] = ""

@app.post("/api/brands")
def create_brand(payload: BrandPayload):
    sb = _sb()
    code = payload.code or payload.name[:3].upper()
    try:
        resp = sb.table("brands").insert({
            "name": payload.name.strip(),
            "code": code,
        }).execute()
        return resp.data[0] if resp.data else {"name": payload.name, "code": code}
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            existing = sb.table("brands").select("*").eq("name", payload.name).single().execute()
            return existing.data
        raise HTTPException(status_code=400, detail=str(e))


# ── POST /api/parse/product ───────────────────────────────────────
class ParsePayload(BaseModel):
    text: str

PARSE_PROMPT = """You are a solar warehouse assistant in India. Parse the user's text and extract product information.
Return ONLY a valid JSON object — no explanation, no markdown, no backticks.

Fields:
- brand: manufacturer/company name (e.g. "Waaree", "Polycab", "Nexus Solar")
- spec: size/wattage/rating (e.g. "650", "3kw", "540W", "2kw")
- type: variant (e.g. "DCR", "N-DCR", "1P", "3P", "Mono", blank if unknown)
- category: exactly one of [Solar Panel, Inverter, Cable, ACDB/DCDB, PVC Material, Structure]
- unit: exactly one of [nos, meters, sets, pcs]
- quantity: number if mentioned, else 0

Rules:
- "panel", "solar", "watt", "DCR", "N-DCR", "bifacial" → Solar Panel, unit=nos
- "inverter", "kw", "1P", "3P", "single phase", "three phase" → Inverter, unit=nos
- "cable", "wire", "meter" → Cable, unit=meters
- "ACDB", "DCDB", "distribution box" → ACDB/DCDB, unit=nos
- "pipe", "bend", "elbow", "UPVC", "tee", "MC4" → PVC Material, unit=pcs
- "structure", "GI", "GP", "mounting", "channel", "purlin", "rafter", "leg", "clamp", "set" → Structure, unit=sets

Examples:
"Waaree 650W DCR panel" → {"brand":"Waaree","spec":"650","type":"DCR","category":"Solar Panel","unit":"nos","quantity":0}
"Nexus Solar 540W DCR panel" → {"brand":"Nexus Solar","spec":"540","type":"DCR","category":"Solar Panel","unit":"nos","quantity":0}
"GI Structure 2kw mounting set" → {"brand":"GI Structure","spec":"2kw","type":"","category":"Structure","unit":"sets","quantity":0}
"Polycab 5kw 3P inverter 10 nos" → {"brand":"Polycab","spec":"5kw","type":"3P","category":"Inverter","unit":"nos","quantity":10}
"Havells DC cable 500 meters" → {"brand":"Havells","spec":"DC","type":"","category":"Cable","unit":"meters","quantity":500}

Text to parse: """

@app.post("/api/parse/product")
def parse_product(payload: ParsePayload):
    """Send free text to Groq and return structured product fields."""
    groq_key = os.environ.get("GROQ_API_KEY")
    if not groq_key:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY not set")

    from groq import Groq
    client = Groq(api_key=groq_key)

    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{
                "role": "user",
                "content": PARSE_PROMPT + payload.text
            }],
            max_tokens=300,
            temperature=0.1,
        )
        raw = completion.choices[0].message.content.strip()
        # Strip any accidental markdown
        raw = raw.strip("`").strip()
        if raw.startswith("json"):
            raw = raw[4:].strip()
        result = json.loads(raw)
        return result
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=422, detail=f"Groq returned invalid JSON: {raw}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── POST /api/products/add ────────────────────────────────────────
class AddProductPayload(BaseModel):
    category: str
    brand:    str
    spec:     Optional[str] = ""
    type_:    Optional[str] = ""
    unit:     Optional[str] = "nos"
    quantity: Optional[int] = 0

@app.post("/api/products/add")
def add_product(payload: AddProductPayload):
    """Add a new product to the products table with auto-generated product_id."""
    sb = _sb()

    CAT_CODES = {
        "solar panel": "SP", "inverter": "INV",
        "acdb/dcdb": "ACDB", "acdb": "ACDB", "dcdb": "DCDB",
        "cable": "CAB", "pvc material": "PVC", "structure": "STR",
    }

    cat_key  = payload.category.strip().lower()
    cat_code = CAT_CODES.get(cat_key, "GEN")

    # Try to find brand code from brands table, else use first 3 chars
    try:
        brand_row = sb.table("brands").select("code") \
                      .ilike("name", payload.brand.strip()).limit(1).execute()
        brand_code = brand_row.data[0]["code"] if brand_row.data else payload.brand[:3].upper()
    except Exception:
        brand_code = payload.brand[:3].upper()

    prefix = f"{cat_code}-{brand_code}-"

    # Auto-increment product_id — always scan live to avoid race with prior inserts
    existing = sb.table("products").select("product_id") \
                 .like("product_id", f"{prefix}%").execute()
    nums = []
    for row in existing.data:
        try:
            nums.append(int(row["product_id"].split("-")[-1]))
        except ValueError:
            pass
    next_num   = max(nums, default=0) + 1
    product_id = f"{prefix}{next_num:03d}"

    # Sort order: after last product in same category
    cat_rows = sb.table("products").select("sort_order") \
                 .eq("category", payload.category) \
                 .order("sort_order", desc=True).limit(1).execute()
    if cat_rows.data:
        sort_order = (cat_rows.data[0].get("sort_order") or 0) + 1
    else:
        all_rows = sb.table("products").select("sort_order") \
                     .order("sort_order", desc=True).limit(1).execute()
        sort_order = (all_rows.data[0].get("sort_order") or 0) + 1 if all_rows.data else 1

    qty    = payload.quantity or 0
    status = _status(qty)

    record = {
        "product_id": product_id,
        "brand":      payload.brand.strip(),
        "spec":       payload.spec  or "",
        "type_":      payload.type_ or "",
        "quantity":   qty,
        "rate":       0,
        "total":      0,
        "status":     status,
        "unit":       payload.unit or "nos",
        "category":   payload.category.strip(),
        "sort_order": sort_order,
    }

    # Retry once on duplicate product_id (race condition / stale cache)
    for attempt in range(2):
        try:
            sb.table("products").insert({**record, "product_id": product_id}).execute()
            return {
                "success":    True,
                "product_id": product_id,
                "brand":      payload.brand,
                "spec":       payload.spec,
                "type_":      payload.type_,
                "category":   payload.category,
                "unit":       payload.unit,
                "quantity":   qty,
            }
        except Exception as e:
            err_str = str(e)
            if "duplicate" in err_str.lower() or "23505" in err_str:
                # Scan again and use next number
                existing2 = sb.table("products").select("product_id") \
                              .like("product_id", f"{prefix}%").execute()
                nums2 = []
                for row in existing2.data:
                    try: nums2.append(int(row["product_id"].split("-")[-1]))
                    except ValueError: pass
                next_num   = max(nums2, default=0) + 1
                product_id = f"{prefix}{next_num:03d}"
                if attempt == 1:
                    raise HTTPException(status_code=400,
                        detail=f"Product ID {product_id} conflict — please try again")
            else:
                raise HTTPException(status_code=400, detail=err_str)


# ── POST /api/stock/in ────────────────────────────────────────────
class StockInItem(BaseModel):
    product_id: str
    brand:      str
    spec:       Optional[str] = ""
    type_:      Optional[str] = ""
    quantity:   int
    unit:       Optional[str] = "nos"

class StockInPayload(BaseModel):
    party:    Optional[str] = ""
    operator: Optional[str] = "Frontend"
    items:    List[StockInItem]

@app.post("/api/stock/in")
def stock_in(payload: StockInPayload):
    sb      = _sb()
    results = []
    errors  = []

    for item in payload.items:
        try:
            resp = sb.table("products").select("id,quantity,rate") \
                     .eq("product_id", item.product_id).single().execute()
            if not resp.data:
                errors.append(f"{item.brand} {item.spec}: product not found")
                continue

            product     = resp.data
            current_qty = int(product.get("quantity") or 0)
            new_qty     = current_qty + item.quantity
            rate        = float(product.get("rate") or 0)
            total       = int(new_qty * rate) if rate > 0 else 0

            sb.table("products").update({
                "quantity": new_qty,
                "status":   _status(new_qty),
                "total":    total,
            }).eq("product_id", item.product_id).execute()

            spec_full = f"{item.spec} {item.type_}".strip()
            sb.table("transactions").insert({
                "timestamp":    datetime.now(IST).isoformat(),
                "type_":        "ADD_IN",
                "brand":        item.brand,
                "spec":         spec_full,
                "qty_change":   item.quantity,
                "stock_before": current_qty,
                "stock_after":  new_qty,
                "vehicle_no":   "",
                "operator":     payload.operator,
                "party":        payload.party,
            }).execute()

            results.append({
                "product_id": item.product_id,
                "brand":      item.brand,
                "spec":       item.spec,
                "type_":      item.type_,
                "quantity":   item.quantity,
                "before":     current_qty,
                "after":      new_qty,
                "unit":       item.unit,
            })

        except Exception as e:
            errors.append(f"{item.brand} {item.spec}: {str(e)}")

    return {"success": len(results) > 0, "results": results, "errors": errors}


# ── POST /api/stock/out ───────────────────────────────────────────
class StockOutItem(BaseModel):
    product_id: str
    brand:      str
    spec:       Optional[str] = ""
    type_:      Optional[str] = ""
    quantity:   int
    unit:       Optional[str] = "nos"

class StockOutPayload(BaseModel):
    vehicle_no: str
    party:      Optional[str] = ""
    operator:   Optional[str] = "Frontend"
    items:      List[StockOutItem]

@app.post("/api/stock/out")
def stock_out(payload: StockOutPayload):
    sb      = _sb()
    results = []
    errors  = []

    for item in payload.items:
        try:
            resp = sb.table("products").select("id,quantity,rate,status") \
                     .eq("product_id", item.product_id).single().execute()
            if not resp.data:
                errors.append(f"{item.brand} {item.spec}: product not found")
                continue

            product     = resp.data
            current_qty = int(product.get("quantity") or 0)

            if current_qty < item.quantity:
                errors.append(f"{item.brand} {item.spec}: sirf {current_qty} hai, {item.quantity} chahiye")
                continue

            new_qty = current_qty - item.quantity
            rate    = float(product.get("rate") or 0)
            total   = int(new_qty * rate) if rate > 0 else 0

            sb.table("products").update({
                "quantity": new_qty,
                "status":   _status(new_qty),
                "total":    total,
            }).eq("product_id", item.product_id).execute()

            spec_full = f"{item.spec} {item.type_}".strip()
            sb.table("transactions").insert({
                "timestamp":    datetime.now(IST).isoformat(),
                "type_":        "SHIP_OUT",
                "brand":        item.brand,
                "spec":         spec_full,
                "qty_change":   -item.quantity,
                "stock_before": current_qty,
                "stock_after":  new_qty,
                "vehicle_no":   payload.vehicle_no,
                "operator":     payload.operator,
                "party":        payload.party,
            }).execute()

            results.append({
                "product_id": item.product_id,
                "brand":      item.brand,
                "spec":       item.spec,
                "type_":      item.type_,
                "quantity":   item.quantity,
                "before":     current_qty,
                "after":      new_qty,
            })

        except Exception as e:
            errors.append(f"{item.brand} {item.spec}: {str(e)}")

    return {"success": len(results) > 0, "results": results, "errors": errors}


# ── PATCH /api/products/rate ──────────────────────────────────────
class RatePayload(BaseModel):
    product_id: str
    rate:       float

@app.patch("/api/products/rate")
def update_rate(payload: RatePayload):
    sb   = _sb()
    resp = sb.table("products").select("quantity") \
             .eq("product_id", payload.product_id).single().execute()
    if not resp.data:
        raise HTTPException(status_code=404, detail="Product not found")

    qty   = int(resp.data.get("quantity") or 0)
    total = int(qty * payload.rate) if payload.rate > 0 else 0

    sb.table("products").update({
        "rate":  payload.rate,
        "total": total,
    }).eq("product_id", payload.product_id).execute()

    return {"success": True, "product_id": payload.product_id,
            "rate": payload.rate, "total": total}


# ── POST /api/challan/pdf ─────────────────────────────────────────
class ChallanItem(BaseModel):
    brand:    str
    spec:     Optional[str] = ""
    type:     Optional[str] = ""
    quantity: int
    unit:     Optional[str] = "nos"

class ChallanPayload(BaseModel):
    vehicle_no: str
    operator:   Optional[str] = ""
    party:      Optional[str] = ""
    items:      List[ChallanItem]

@app.post("/api/challan/pdf")
def challan_pdf(payload: ChallanPayload):
    try:
        from pdf_generator import generate_delivery_receipt
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"PDF generator import failed: {e}")

    pdf_items = [
        {"brand": i.brand, "spec": i.spec, "type": i.type,
         "quantity": i.quantity, "unit": i.unit}
        for i in payload.items
    ]

    try:
        pdf_bytes = generate_delivery_receipt(
            payload.vehicle_no,
            payload.operator or "Frontend",
            pdf_items,
            payload.party or "",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {e}")

    filename = f"challan_{payload.vehicle_no}_{datetime.now(IST).strftime('%d%b%Y_%H%M')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename={filename}"},
    )


# ── GET /api/challans ─────────────────────────────────────────────
@app.get("/api/challans")
def get_challans():
    """
    Last 7 days SHIP_OUT transactions grouped by vehicle_no + date.
    Returns list of unique challans with their items.
    """
    since = (datetime.now(IST) - timedelta(days=7)).isoformat()
    resp  = _sb().table("transactions").select("*") \
                 .eq("type_", "SHIP_OUT") \
                 .gte("timestamp", since) \
                 .order("timestamp", desc=True) \
                 .execute()

    challans: dict = {}
    for row in resp.data:
        ts      = row.get("timestamp", "") or ""
        date    = ts[:10]  # YYYY-MM-DD
        vehicle = (row.get("vehicle_no") or "UNKNOWN").strip()
        key     = f"{vehicle}_{date}"

        if key not in challans:
            challans[key] = {
                "key":       key,
                "vehicle_no": vehicle,
                "date":      date,
                "party":     row.get("party")    or "",
                "operator":  row.get("operator") or "",
                "items":     [],
            }

        challans[key]["items"].append({
            "brand":     row.get("brand", ""),
            "spec":      row.get("spec",  "") or "",
            "quantity":  abs(int(row.get("qty_change", 0) or 0)),
            "timestamp": ts,
        })

    return sorted(challans.values(), key=lambda c: c["date"], reverse=True)


# ── POST /api/stock/edit ──────────────────────────────────────────
class StockEditItem(BaseModel):
    product_id: str
    brand:      str
    spec:       Optional[str] = ""
    type_:      Optional[str] = ""
    quantity:   int
    unit:       Optional[str] = "nos"

class StockEditPayload(BaseModel):
    vehicle_no:     str
    party:          Optional[str] = ""
    operator:       Optional[str] = "Frontend"
    original_items: List[StockEditItem]
    new_items:      List[StockEditItem]

@app.post("/api/stock/edit")
def stock_edit(payload: StockEditPayload):
    """
    Reconcile stock from an edited challan — applies DIFF only.
    - qty increased (e.g. 10→15): deduct 5 more
    - qty decreased (e.g. 10→8):  add back 2
    - item removed:                add back all
    - new item added:              deduct all
    Logs CHALLAN_EDIT transaction per changed item.
    """
    sb = _sb()

    orig_map = {i.product_id: i for i in payload.original_items}
    new_map  = {i.product_id: i for i in payload.new_items}
    all_pids = set(orig_map.keys()) | set(new_map.keys())

    results = []
    errors  = []

    for pid in all_pids:
        orig_qty = orig_map[pid].quantity if pid in orig_map else 0
        new_qty  = new_map[pid].quantity  if pid in new_map  else 0
        diff     = new_qty - orig_qty   # +ve = deduct more, -ve = add back

        if diff == 0:
            continue

        item = new_map.get(pid) or orig_map.get(pid)

        try:
            resp = sb.table("products").select("id,quantity,rate") \
                     .eq("product_id", pid).single().execute()
            if not resp.data:
                errors.append(f"{item.brand} {item.spec}: product not found")
                continue

            product       = resp.data
            current_stock = int(product.get("quantity") or 0)

            if diff > 0 and current_stock < diff:
                errors.append(
                    f"{item.brand} {item.spec}: sirf {current_stock} hai, "
                    f"{diff} aur chahiye"
                )
                continue

            new_stock = current_stock - diff   # negative diff = add back = increase stock
            rate      = float(product.get("rate") or 0)
            total     = int(new_stock * rate) if rate > 0 else 0

            sb.table("products").update({
                "quantity": new_stock,
                "status":   _status(new_stock),
                "total":    total,
            }).eq("product_id", pid).execute()

            spec_full = f"{item.spec or ''} {item.type_ or ''}".strip()
            sb.table("transactions").insert({
                "timestamp":    datetime.now(IST).isoformat(),
                "type_":        "CHALLAN_EDIT",
                "brand":        item.brand,
                "spec":         spec_full,
                "qty_change":   -diff,    # negative = stock went up (add-back)
                "stock_before": current_stock,
                "stock_after":  new_stock,
                "vehicle_no":   payload.vehicle_no,
                "operator":     payload.operator,
                "party":        payload.party,
            }).execute()

            results.append({
                "product_id": pid,
                "brand":      item.brand,
                "spec":       item.spec,
                "diff":       diff,
                "before":     current_stock,
                "after":      new_stock,
            })

        except Exception as e:
            errors.append(f"{item.brand} {item.spec}: {str(e)}")

    return {"success": len(results) > 0 or len(errors) == 0,
            "results": results, "errors": errors}


# ── GET /health ───────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok"}
