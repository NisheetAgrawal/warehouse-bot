"""
api_server.py — REST API for the Swadev Energies Warehouse frontend.
Run: uvicorn api_server:app --reload --port 8000

Endpoints:
  GET   /api/products           — all products from Supabase
  GET   /api/products/stats     — aggregate counts (in/low/out of stock)
  GET   /api/transactions       — recent 100 transactions
  POST  /api/stock/in           — add incoming stock, log ADD_IN transactions
  POST  /api/stock/out          — deduct stock for a shipment, log SHIP_OUT transactions
  PATCH /api/products/rate      — update rate (and recompute total) for a product
  POST  /api/challan/pdf        — generate delivery challan PDF (returns binary)
"""

import os, sys
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
    """Add incoming stock. Logs ADD_IN transaction per item."""
    sb      = _sb()
    results = []
    errors  = []

    for item in payload.items:
        try:
            resp = sb.table("products") \
                     .select("id,quantity,rate") \
                     .eq("product_id", item.product_id) \
                     .single().execute()
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
    """Deduct stock for each item. Logs SHIP_OUT transaction per item."""
    sb      = _sb()
    results = []
    errors  = []

    for item in payload.items:
        try:
            resp = sb.table("products") \
                     .select("id,quantity,rate,status") \
                     .eq("product_id", item.product_id) \
                     .single().execute()
            if not resp.data:
                errors.append(f"{item.brand} {item.spec}: product not found")
                continue

            product     = resp.data
            current_qty = int(product.get("quantity") or 0)

            if current_qty < item.quantity:
                errors.append(
                    f"{item.brand} {item.spec}: sirf {current_qty} hai, "
                    f"{item.quantity} chahiye"
                )
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
    """Update the rate for a product and recompute total."""
    sb = _sb()
    resp = sb.table("products") \
             .select("quantity") \
             .eq("product_id", payload.product_id) \
             .single().execute()
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
    """Generate delivery challan PDF and return as inline binary."""
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

    filename = (
        f"challan_{payload.vehicle_no}_"
        f"{datetime.now(IST).strftime('%d%b%Y_%H%M')}.pdf"
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename={filename}"},
    )


# ── GET /health ───────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok"}
