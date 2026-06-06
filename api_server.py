"""
api_server.py — REST API for the Swadev Energies Warehouse frontend.
Run: uvicorn api_server:app --reload --port 8000

Endpoints:
  GET  /api/products        — all products from Supabase
  GET  /api/products/stats  — aggregate counts (in/low/out of stock)
"""

import os
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client

app = FastAPI(title="Swadev Warehouse API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten in production
    allow_methods=["*"],
    allow_headers=["*"],
)

def _sb():
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])


@app.get("/api/products")
def get_products():
    """All products ordered by sort_order."""
    resp = _sb().table("products").select("*").order("sort_order").execute()
    return resp.data


@app.get("/api/products/stats")
def get_stats():
    """Quick counts for the dashboard stats strip."""
    resp = _sb().table("products").select("quantity").execute()
    products = resp.data
    return {
        "in_stock":   sum(1 for p in products if (p.get("quantity") or 0) >= 5),
        "low_stock":  sum(1 for p in products if 0 < (p.get("quantity") or 0) < 5),
        "out_stock":  sum(1 for p in products if (p.get("quantity") or 0) == 0),
        "total":      len(products),
    }


@app.get("/api/transactions")
def get_transactions():
    """Recent 100 transactions, newest first."""
    resp = _sb().table("transactions").select("*").order("timestamp", desc=True).limit(100).execute()
    return resp.data


@app.get("/health")
def health():
    return {"status": "ok"}
