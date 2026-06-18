import { useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import { useProducts } from "../hooks/useProducts"
import { getName } from "../lib/auth"
import ProductSearch from "../components/ProductSearch"
import QtyControl from "../components/QtyControl"
import BottomNav from "../components/BottomNav"

const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000"

const CAT_EMOJI = {
  "Solar Panel": "☀️", "Inverter": "⚡", "ACDB/DCDB": "🔌",
  "Cable": "🔗", "PVC Material": "🧱", "Structure": "🏗️", "General": "📦",
}

export default function StockIn() {
  const navigate = useNavigate()
  const { products, loading: productsLoading, search } = useProducts()

  const [party, setParty]       = useState("")
  const [items, setItems]       = useState([])   // [{product, qty}]
  const [submitting, setSubmitting] = useState(false)
  const [results, setResults]   = useState(null) // success results
  const [errors, setErrors]     = useState([])

  useEffect(() => {
    if (!localStorage.getItem("auth")) navigate("/login", { replace: true })
  }, [navigate])

  function addProduct(product) {
    setItems((prev) => {
      const idx = prev.findIndex((i) => i.product.product_id === product.product_id)
      if (idx !== -1) {
        const next = [...prev]
        next[idx] = { ...next[idx], qty: next[idx].qty + 1 }
        return next
      }
      return [...prev, { product, qty: 1 }]
    })
  }

  function changeQty(productId, delta) {
    setItems((prev) =>
      prev
        .map((i) => i.product.product_id === productId ? { ...i, qty: i.qty + delta } : i)
        .filter((i) => i.qty > 0)
    )
  }

  function setQtyDirect(productId, newQty) {
    setItems((prev) =>
      prev.map((i) =>
        i.product.product_id === productId ? { ...i, qty: Math.max(1, newQty) } : i
      )
    )
  }

  async function handleSubmit() {
    if (items.length === 0) return
    setSubmitting(true)
    setErrors([])
    try {
      const res = await fetch(`${BASE}/api/stock/in`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          party,
          operator: getName(),
          items: items.map(({ product, qty }) => ({
            product_id: product.product_id,
            brand:      product.brand,
            spec:       product.spec  || "",
            type_:      product.type_ || "",
            quantity:   qty,
            unit:       product.unit  || "nos",
          })),
        }),
      })
      const data = await res.json()
      if (data.errors?.length) setErrors(data.errors)
      if (data.results?.length) setResults(data.results)
    } catch (err) {
      setErrors([`Network error: ${err.message}`])
    } finally {
      setSubmitting(false)
    }
  }

  // ── Success screen ─────────────────────────────────────────────
  if (results) {
    return (
      <div
        className="min-h-dvh flex flex-col px-5 pb-28"
        style={{ backgroundColor: "#0A0A0F", fontFamily: "'DM Sans', sans-serif" }}
      >
        {/* Header */}
        <div className="flex items-center gap-3 pt-14 pb-6">
          <button
            onClick={() => navigate("/home")}
            className="flex items-center justify-center w-9 h-9 rounded-xl"
            style={{ background: "rgba(255,255,255,0.07)", border: "none", cursor: "pointer" }}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
                 stroke="rgba(255,255,255,0.8)" strokeWidth="2.2"
                 strokeLinecap="round" strokeLinejoin="round">
              <polyline points="15 18 9 12 15 6" />
            </svg>
          </button>
          <h1 style={{ fontSize: 17, fontWeight: 600, color: "#fff", margin: 0 }}>
            Stock Updated ✅
          </h1>
        </div>

        {/* Success animation */}
        <div className="flex flex-col items-center py-6">
          <div
            className="flex items-center justify-center rounded-full mb-4"
            style={{
              width: 72, height: 72,
              backgroundColor: "rgba(52,211,153,0.15)",
              border: "2px solid rgba(52,211,153,0.4)",
              animation: "pop 0.4s cubic-bezier(0.34,1.56,0.64,1) both",
            }}
          >
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none"
                 stroke="#34D399" strokeWidth="2.5"
                 strokeLinecap="round" strokeLinejoin="round">
              <polyline points="20 6 9 17 4 12" />
            </svg>
          </div>
          {party && (
            <p style={{ fontSize: 13, color: "rgba(255,255,255,0.45)", margin: 0 }}>
              Supplier: <span style={{ color: "#fff", fontWeight: 600 }}>{party}</span>
            </p>
          )}
        </div>

        {/* Before → After results */}
        <div className="flex flex-col gap-2">
          {results.map((r) => (
            <div
              key={r.product_id}
              className="rounded-2xl px-4 py-3"
              style={{
                background: "rgba(52,211,153,0.06)",
                border: "1px solid rgba(52,211,153,0.2)",
              }}
            >
              <p style={{ margin: 0, fontSize: 13, fontWeight: 600, color: "#fff" }}>
                {r.brand} {r.spec} {r.type_}
              </p>
              <div className="flex items-center gap-2 mt-1">
                <span style={{
                  fontSize: 13, fontFamily: "'DM Mono', monospace",
                  color: "rgba(255,255,255,0.4)",
                }}>
                  {r.before}
                </span>
                <span style={{ fontSize: 11, color: "rgba(255,255,255,0.25)" }}>→</span>
                <span style={{
                  fontSize: 15, fontWeight: 700, fontFamily: "'DM Mono', monospace",
                  color: "#34D399",
                }}>
                  {r.after}
                </span>
                <span style={{ fontSize: 11, color: "rgba(255,255,255,0.35)" }}>
                  (+{r.quantity} {r.unit})
                </span>
              </div>
            </div>
          ))}

          {errors.map((e, i) => (
            <div
              key={i}
              className="rounded-2xl px-4 py-3"
              style={{
                background: "rgba(248,113,113,0.08)",
                border: "1px solid rgba(248,113,113,0.25)",
              }}
            >
              <p style={{ margin: 0, fontSize: 13, color: "#F87171" }}>❌ {e}</p>
            </div>
          ))}
        </div>

        <button
          onClick={() => { setResults(null); setItems([]); setParty(""); setErrors([]) }}
          className="w-full rounded-2xl py-4 mt-6"
          style={{
            backgroundColor: "#E8500A", border: "none", cursor: "pointer",
            fontFamily: "'DM Sans', sans-serif", fontSize: 15,
            fontWeight: 600, color: "#fff",
          }}
        >
          Aur Maal Add Karo
        </button>

        <style>{`@keyframes pop{from{transform:scale(.5);opacity:0}to{transform:scale(1);opacity:1}}`}</style>
        <BottomNav active="stock" />
      </div>
    )
  }

  // ── Main form ──────────────────────────────────────────────────
  return (
    <div
      className="min-h-dvh flex flex-col pb-28"
      style={{ backgroundColor: "#0A0A0F", fontFamily: "'DM Sans', sans-serif" }}
    >
      {/* Header */}
      <div className="flex items-center gap-3 px-5 pt-14 pb-5">
        <button
          onClick={() => navigate("/home")}
          className="flex items-center justify-center w-9 h-9 rounded-xl"
          style={{ background: "rgba(255,255,255,0.07)", border: "none", cursor: "pointer" }}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
               stroke="rgba(255,255,255,0.8)" strokeWidth="2.2"
               strokeLinecap="round" strokeLinejoin="round">
            <polyline points="15 18 9 12 15 6" />
          </svg>
        </button>
        <div>
          <h1 style={{ fontSize: 17, fontWeight: 600, color: "#fff", margin: 0 }}>
            Maal Aaya
          </h1>
          <p style={{ fontSize: 12, color: "rgba(255,255,255,0.35)", margin: 0 }}>
            Incoming stock update karo
          </p>
        </div>
      </div>

      <div className="px-5 flex flex-col gap-4">
        {/* Party input */}
        <div>
          <p style={{
            fontSize: 11, color: "rgba(255,255,255,0.35)", margin: "0 0 8px",
            textTransform: "uppercase", letterSpacing: "0.06em",
          }}>
            Supplier / Party (optional)
          </p>
          <input
            value={party}
            onChange={(e) => setParty(e.target.value)}
            placeholder="Kis se aaya maal"
            className="w-full rounded-2xl px-4 py-4 text-white outline-none"
            style={{
              background: "rgba(255,255,255,0.05)",
              border: "1.5px solid rgba(255,255,255,0.08)",
              fontFamily: "'DM Sans', sans-serif",
              fontSize: 15, boxSizing: "border-box",
            }}
          />
        </div>

        {/* Product search */}
        <div>
          <p style={{
            fontSize: 11, color: "rgba(255,255,255,0.35)", margin: "0 0 8px",
            textTransform: "uppercase", letterSpacing: "0.06em",
          }}>
            Product Chunno
          </p>
          <ProductSearch
            search={search}
            onSelect={addProduct}
            loading={productsLoading}
            isSelected={(id) => items.some((i) => i.product.product_id === id)}
          />
        </div>

        {/* Items list */}
        {items.length === 0 ? (
          <div
            className="flex flex-col items-center justify-center py-10 gap-2"
            style={{ color: "rgba(255,255,255,0.2)" }}
          >
            <span style={{ fontSize: 36 }}>📦</span>
            <p style={{ fontSize: 13, margin: 0 }}>
              Upar search karo, product add karo
            </p>
          </div>
        ) : (
          <div className="flex flex-col gap-2">
            {items.map(({ product, qty }) => (
              <div
                key={product.product_id}
                className="flex items-center gap-3 px-4 py-3 rounded-2xl"
                style={{
                  background: "rgba(255,255,255,0.05)",
                  border: "1px solid rgba(255,255,255,0.08)",
                }}
              >
                <span style={{ fontSize: 18, flexShrink: 0 }}>
                  {CAT_EMOJI[product.category] || "📦"}
                </span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <p style={{
                    margin: 0, fontSize: 13, fontWeight: 600, color: "#fff",
                    overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                  }}>
                    {product.brand}
                    {product.spec  ? ` ${product.spec}`  : ""}
                    {product.type_ ? ` ${product.type_}` : ""}
                  </p>
                  <p style={{
                    margin: 0, fontSize: 11, color: "rgba(255,255,255,0.35)",
                    fontFamily: "'DM Mono', monospace",
                  }}>
                    Stock mein abhi: {product.quantity ?? 0}
                  </p>
                </div>
                {/* Fix 2: tappable QtyControl */}
                <QtyControl
                  qty={qty}
                  productId={product.product_id}
                  onDelta={changeQty}
                  onDirectSet={setQtyDirect}
                />
              </div>
            ))}
          </div>
        )}

        {/* Errors */}
        {errors.map((e, i) => (
          <p key={i} style={{ margin: 0, fontSize: 13, color: "#F87171" }}>❌ {e}</p>
        ))}

        {/* Submit */}
        <button
          onClick={handleSubmit}
          disabled={items.length === 0 || submitting}
          className="w-full rounded-2xl py-4"
          style={{
            backgroundColor: items.length === 0 || submitting
              ? "rgba(232,80,10,0.35)" : "#E8500A",
            border: "none",
            cursor: items.length === 0 || submitting ? "not-allowed" : "pointer",
            fontFamily: "'DM Sans', sans-serif",
            fontSize: 15, fontWeight: 600, color: "#fff",
          }}
        >
          {submitting ? "Update ho raha hai..." : "Stock Update Karo ✓"}
        </button>
      </div>

      <BottomNav active="stock" />
    </div>
  )
}
