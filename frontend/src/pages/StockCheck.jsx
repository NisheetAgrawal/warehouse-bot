import { useEffect, useRef, useState } from "react"
import { useNavigate } from "react-router-dom"
import { useProducts } from "../hooks/useProducts"
import ProductSearch from "../components/ProductSearch"
import BottomNav from "../components/BottomNav"

const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000"

const CAT_EMOJI = {
  "Solar Panel": "☀️", "Inverter": "⚡", "ACDB/DCDB": "🔌",
  "Cable": "🔗", "PVC Material": "🧱", "Structure": "🏗️", "General": "📦",
}

function StockBadge({ qty }) {
  if (qty === 0) return (
    <span style={{
      fontSize: 12, fontWeight: 600, padding: "4px 12px", borderRadius: 20,
      backgroundColor: "rgba(248,113,113,0.15)", color: "#F87171",
      border: "1px solid rgba(248,113,113,0.3)",
    }}>Out of Stock</span>
  )
  if (qty < 5) return (
    <span style={{
      fontSize: 12, fontWeight: 600, padding: "4px 12px", borderRadius: 20,
      backgroundColor: "rgba(250,204,21,0.15)", color: "#FACC15",
      border: "1px solid rgba(250,204,21,0.3)",
    }}>Low Stock</span>
  )
  return (
    <span style={{
      fontSize: 12, fontWeight: 600, padding: "4px 12px", borderRadius: 20,
      backgroundColor: "rgba(52,211,153,0.15)", color: "#34D399",
      border: "1px solid rgba(52,211,153,0.3)",
    }}>In Stock</span>
  )
}

function RateEditor({ product, onSaved }) {
  const [editing, setEditing]   = useState(false)
  const [value, setValue]       = useState(product.rate?.toString() || "")
  const [saving, setSaving]     = useState(false)
  const [saved, setSaved]       = useState(false)
  const inputRef = useRef(null)

  useEffect(() => {
    if (editing && inputRef.current) inputRef.current.focus()
  }, [editing])

  async function save() {
    const rate = parseFloat(value)
    if (isNaN(rate) || rate < 0) { setEditing(false); return }
    setSaving(true)
    try {
      await fetch(`${BASE}/api/products/rate`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ product_id: product.product_id, rate }),
      })
      setSaved(true)
      setEditing(false)
      onSaved?.(rate)
      setTimeout(() => setSaved(false), 2000)
    } catch (e) {
      console.error(e)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      {editing ? (
        <>
          <span style={{ fontSize: 14, color: "rgba(255,255,255,0.4)" }}>₹</span>
          <input
            ref={inputRef}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onBlur={save}
            onKeyDown={(e) => e.key === "Enter" && save()}
            type="number"
            min="0"
            className="outline-none text-white"
            style={{
              background: "rgba(255,255,255,0.08)",
              border: "1.5px solid #E8500A",
              borderRadius: 10,
              padding: "6px 10px",
              fontFamily: "'DM Mono', monospace",
              fontSize: 16, fontWeight: 600,
              width: 120,
              color: "#fff",
            }}
          />
          <span style={{ fontSize: 12, color: "rgba(255,255,255,0.35)" }}>
            Enter ya blur to save
          </span>
        </>
      ) : (
        <>
          <span style={{
            fontSize: 20, fontWeight: 700, color: "#fff",
            fontFamily: "'DM Mono', monospace",
          }}>
            {value ? `₹${parseFloat(value).toLocaleString("en-IN")}` : "—"}
          </span>
          <span style={{ fontSize: 12, color: "rgba(255,255,255,0.35)" }}>/ unit</span>
          <button
            onClick={() => setEditing(true)}
            title="Edit rate"
            style={{
              background: "rgba(255,255,255,0.08)", border: "none",
              borderRadius: 8, padding: "6px 8px", cursor: "pointer",
              display: "flex", alignItems: "center",
            }}
          >
            {saved ? (
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
                   stroke="#34D399" strokeWidth="2.5"
                   strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12" />
              </svg>
            ) : (
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
                   stroke="rgba(255,255,255,0.5)" strokeWidth="2"
                   strokeLinecap="round" strokeLinejoin="round">
                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
              </svg>
            )}
          </button>
        </>
      )}
    </div>
  )
}

export default function StockCheck() {
  const navigate = useNavigate()
  const { loading: productsLoading, search } = useProducts()
  const [selected, setSelected] = useState(null)
  const [localRate, setLocalRate] = useState(null)

  useEffect(() => {
    if (!localStorage.getItem("auth")) navigate("/login", { replace: true })
  }, [navigate])

  function handleSelect(product) {
    setSelected(product)
    setLocalRate(null)
  }

  const qty    = selected?.quantity ?? 0
  const rate   = localRate ?? selected?.rate ?? 0
  const total  = qty > 0 && rate > 0 ? qty * rate : null

  return (
    <div
      className="min-h-dvh flex flex-col pb-28"
      style={{ backgroundColor: "#0A0A0F", fontFamily: "'DM Sans', sans-serif" }}
    >
      {/* Header */}
      <div className="flex items-center gap-3 px-5 pt-14 pb-5">
        <button
          onClick={() => navigate("/home")}
          style={{
            display: "flex", alignItems: "center", justifyContent: "center",
            width: 36, height: 36, borderRadius: 12,
            background: "rgba(255,255,255,0.07)", border: "none", cursor: "pointer",
          }}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
               stroke="rgba(255,255,255,0.8)" strokeWidth="2.2"
               strokeLinecap="round" strokeLinejoin="round">
            <polyline points="15 18 9 12 15 6" />
          </svg>
        </button>
        <div>
          <h1 style={{ fontSize: 17, fontWeight: 600, color: "#fff", margin: 0 }}>
            Stock Check
          </h1>
          <p style={{ fontSize: 12, color: "rgba(255,255,255,0.35)", margin: 0 }}>
            Koi bhi product dhundho
          </p>
        </div>
      </div>

      <div className="px-5 flex flex-col gap-4">
        {/* Search */}
        <ProductSearch
          search={search}
          onSelect={handleSelect}
          loading={productsLoading}
          placeholder="Brand, spec ya category likhein..."
        />

        {/* Product card */}
        {selected ? (
          <div
            className="rounded-3xl p-5 flex flex-col gap-4"
            style={{
              background: "rgba(255,255,255,0.04)",
              border: "1px solid rgba(255,255,255,0.08)",
            }}
          >
            {/* Category + badge */}
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <span style={{
                fontSize: 11, color: "rgba(255,255,255,0.35)",
                textTransform: "uppercase", letterSpacing: "0.1em",
                fontFamily: "'DM Sans', sans-serif",
              }}>
                {CAT_EMOJI[selected.category] || "📦"} {selected.category}
              </span>
              <StockBadge qty={qty} />
            </div>

            {/* Product name */}
            <div>
              <h2 style={{
                fontSize: 22, fontWeight: 700, color: "#fff", margin: 0,
                letterSpacing: "-0.3px", lineHeight: 1.2,
              }}>
                {selected.brand}
              </h2>
              {(selected.spec || selected.type_) && (
                <p style={{
                  fontSize: 14, color: "rgba(255,255,255,0.45)", margin: "4px 0 0",
                }}>
                  {selected.spec} {selected.type_}
                </p>
              )}
            </div>

            {/* Divider */}
            <div style={{ height: 1, background: "rgba(255,255,255,0.06)" }} />

            {/* Quantity */}
            <div style={{ display: "flex", alignItems: "flex-end", gap: 8 }}>
              <span style={{
                fontSize: 56, fontWeight: 800, color: qty === 0 ? "#F87171" : "#fff",
                fontFamily: "'DM Mono', monospace",
                lineHeight: 1, letterSpacing: "-2px",
              }}>
                {qty}
              </span>
              <span style={{
                fontSize: 14, color: "rgba(255,255,255,0.4)",
                marginBottom: 8, fontFamily: "'DM Sans', sans-serif",
              }}>
                {selected.unit || "nos"}
              </span>
            </div>

            {/* Divider */}
            <div style={{ height: 1, background: "rgba(255,255,255,0.06)" }} />

            {/* Rate editor */}
            <div>
              <p style={{
                fontSize: 11, color: "rgba(255,255,255,0.35)", margin: "0 0 8px",
                textTransform: "uppercase", letterSpacing: "0.08em",
              }}>
                Rate per unit
              </p>
              <RateEditor
                product={selected}
                onSaved={(r) => setLocalRate(r)}
              />
            </div>

            {/* Total value */}
            {total && (
              <>
                <div style={{ height: 1, background: "rgba(255,255,255,0.06)" }} />
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <p style={{
                    fontSize: 12, color: "rgba(255,255,255,0.35)", margin: 0,
                    textTransform: "uppercase", letterSpacing: "0.08em",
                  }}>
                    Total Value
                  </p>
                  <p style={{
                    fontSize: 18, fontWeight: 700, color: "#E8500A", margin: 0,
                    fontFamily: "'DM Mono', monospace",
                  }}>
                    ₹{(qty * rate).toLocaleString("en-IN")}
                  </p>
                </div>
              </>
            )}

            {/* Product ID */}
            <p style={{
              fontSize: 10, color: "rgba(255,255,255,0.2)", margin: 0,
              fontFamily: "'DM Mono', monospace",
            }}>
              {selected.product_id}
            </p>
          </div>
        ) : (
          /* Empty state */
          <div
            className="flex flex-col items-center justify-center py-16 gap-3"
            style={{ color: "rgba(255,255,255,0.2)" }}
          >
            <span style={{ fontSize: 48 }}>🔍</span>
            <p style={{ fontSize: 13, margin: 0, fontFamily: "'DM Sans', sans-serif" }}>
              Koi product search karo
            </p>
            <p style={{ fontSize: 11, margin: 0, color: "rgba(255,255,255,0.15)" }}>
              Brand name, spec ya category
            </p>
          </div>
        )}
      </div>

      <BottomNav active="stock" />
    </div>
  )
}
