import { useEffect, useMemo, useState } from "react"
import { useNavigate } from "react-router-dom"
import { api } from "../lib/api"
import BottomNav from "../components/BottomNav"

const CAT_EMOJI = {
  "Solar Panel": "☀️", "Inverter": "⚡", "ACDB/DCDB": "🔌",
  "Cable": "🔗", "PVC Material": "🧱", "Structure": "🏗️", "General": "📦",
}

const FILTERS = [
  { id: "all",  label: "Sab" },
  { id: "in",   label: "In Stock" },
  { id: "low",  label: "Low" },
  { id: "out",  label: "Out" },
]

function qtyColor(qty) {
  if (qty === 0) return "#F87171"
  if (qty < 5)   return "#FACC15"
  return "#34D399"
}

function StockRow({ product }) {
  const emoji = CAT_EMOJI[product.category] || "📦"
  const qty   = product.quantity || 0
  return (
    <div
      className="flex items-center gap-3 px-4 py-3 rounded-2xl"
      style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.07)" }}
    >
      <span style={{ fontSize: 20, flexShrink: 0 }}>{emoji}</span>
      <div className="flex-1 min-w-0">
        <p className="truncate" style={{ fontSize: 13, fontWeight: 600, color: "#fff",
            fontFamily: "'DM Sans', sans-serif", margin: 0 }}>
          {product.brand}
        </p>
        {(product.spec || product.type_) && (
          <p className="truncate" style={{ fontSize: 11, color: "rgba(255,255,255,0.35)",
              fontFamily: "'DM Sans', sans-serif", margin: 0 }}>
            {product.spec} {product.type_}
          </p>
        )}
      </div>
      <div style={{ textAlign: "right", flexShrink: 0 }}>
        <span style={{ fontSize: 18, fontWeight: 700, color: qtyColor(qty),
            fontFamily: "'DM Mono', monospace" }}>
          {qty}
        </span>
        <span style={{ fontSize: 10, color: "rgba(255,255,255,0.3)", marginLeft: 4 }}>
          {product.unit || "nos"}
        </span>
      </div>
    </div>
  )
}

export default function AllStock() {
  const navigate = useNavigate()
  const [products, setProducts] = useState([])
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState(null)
  const [query, setQuery]       = useState("")
  const [filter, setFilter]     = useState("all")

  useEffect(() => {
    if (!localStorage.getItem("auth")) navigate("/login", { replace: true })
  }, [navigate])

  useEffect(() => {
    api.products()
      .then((data) => { setProducts(data); setLoading(false) })
      .catch((err) => { setError(err.message); setLoading(false) })
  }, [])

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase()
    return products.filter((p) => {
      const qty = p.quantity || 0
      if (filter === "in"  && qty < 5)  return false
      if (filter === "low" && !(qty > 0 && qty < 5)) return false
      if (filter === "out" && qty !== 0) return false
      if (q) {
        const hay = `${p.brand} ${p.spec || ""} ${p.type_ || ""} ${p.category || ""}`.toLowerCase()
        if (!q.split(" ").every((w) => hay.includes(w))) return false
      }
      return true
    })
  }, [products, query, filter])

  return (
    <div className="min-h-dvh flex flex-col pb-28"
         style={{ backgroundColor: "#0A0A0F", fontFamily: "'DM Sans', sans-serif" }}>

      {/* Header */}
      <div className="flex items-center gap-3 px-5 pt-14 pb-4">
        <button
          onClick={() => navigate("/home")}
          style={{ display: "flex", alignItems: "center", justifyContent: "center",
            width: 36, height: 36, borderRadius: 12,
            background: "rgba(255,255,255,0.07)", border: "none", cursor: "pointer" }}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
               stroke="rgba(255,255,255,0.8)" strokeWidth="2.2"
               strokeLinecap="round" strokeLinejoin="round">
            <polyline points="15 18 9 12 15 6" />
          </svg>
        </button>
        <div>
          <h1 style={{ fontSize: 17, fontWeight: 600, color: "#fff", margin: 0 }}>
            All Stock
          </h1>
          <p style={{ fontSize: 12, color: "rgba(255,255,255,0.35)", margin: 0 }}>
            Poora inventory — {products.length} products
          </p>
        </div>
      </div>

      <div className="px-5 flex flex-col gap-3">
        {/* Search */}
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Brand, spec ya category dhundho..."
          className="w-full bg-transparent outline-none text-white text-sm placeholder:text-white/30"
          style={{ fontFamily: "'DM Sans', sans-serif",
            background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.08)",
            borderRadius: 16, padding: "14px 16px" }}
        />

        {/* Filter pills */}
        <div className="flex gap-2">
          {FILTERS.map((f) => {
            const active = filter === f.id
            return (
              <button
                key={f.id}
                onClick={() => setFilter(f.id)}
                style={{ flex: 1, padding: "8px 0", borderRadius: 12, cursor: "pointer",
                  fontSize: 12, fontWeight: 600, fontFamily: "'DM Sans', sans-serif",
                  background: active ? "rgba(232,80,10,0.15)" : "rgba(255,255,255,0.04)",
                  border: `1px solid ${active ? "rgba(232,80,10,0.4)" : "rgba(255,255,255,0.07)"}`,
                  color: active ? "#E8500A" : "rgba(255,255,255,0.5)" }}
              >
                {f.label}
              </button>
            )
          })}
        </div>

        {/* List */}
        {loading && (
          <div className="flex flex-col gap-2">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="rounded-2xl"
                   style={{ height: 56, background: "rgba(255,255,255,0.04)",
                     border: "1px solid rgba(255,255,255,0.07)" }} />
            ))}
          </div>
        )}

        {!loading && error && (
          <p style={{ color: "#F87171", fontSize: 13 }}>API se data nahi aaya: {error}</p>
        )}

        {!loading && !error && visible.length === 0 && (
          <div className="flex flex-col items-center justify-center py-16 gap-3"
               style={{ color: "rgba(255,255,255,0.2)" }}>
            <span style={{ fontSize: 40 }}>📦</span>
            <p style={{ margin: 0, fontSize: 13 }}>Koi product nahi mila</p>
          </div>
        )}

        {!loading && !error && (
          <div className="flex flex-col gap-2">
            {visible.map((p) => <StockRow key={p.id || p.product_id} product={p} />)}
          </div>
        )}
      </div>

      <BottomNav active="stock" />
    </div>
  )
}
