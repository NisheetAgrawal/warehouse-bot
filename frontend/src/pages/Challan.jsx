import { useEffect, useRef, useState } from "react"
import { useNavigate } from "react-router-dom"
import { api } from "../lib/api"

const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000"

const CAT_EMOJI = {
  "Solar Panel":  "☀️",
  "Inverter":     "⚡",
  "ACDB/DCDB":   "🔌",
  "Cable":        "🔗",
  "PVC Material": "🧱",
  "Structure":    "🏗️",
  "General":      "📦",
}

// ── Shared UI atoms ───────────────────────────────────────────────
function BackArrow({ onClick }) {
  return (
    <button
      onClick={onClick}
      className="flex items-center justify-center w-9 h-9 rounded-xl transition-opacity active:opacity-50"
      style={{ background: "rgba(255,255,255,0.07)", border: "none", cursor: "pointer" }}
    >
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
           stroke="rgba(255,255,255,0.8)" strokeWidth="2.2"
           strokeLinecap="round" strokeLinejoin="round">
        <polyline points="15 18 9 12 15 6" />
      </svg>
    </button>
  )
}

function OrangeBtn({ children, onClick, disabled, loading }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled || loading}
      className="w-full rounded-2xl py-4 text-white font-semibold transition-all active:scale-95"
      style={{
        backgroundColor: disabled || loading ? "rgba(232,80,10,0.4)" : "#E8500A",
        border: "none",
        cursor: disabled || loading ? "not-allowed" : "pointer",
        fontFamily: "'DM Sans', sans-serif",
        fontSize: 15,
        fontWeight: 600,
      }}
    >
      {loading ? "..." : children}
    </button>
  )
}

function GhostBtn({ children, onClick }) {
  return (
    <button
      onClick={onClick}
      className="w-full rounded-2xl py-4 font-semibold transition-all active:scale-95"
      style={{
        background: "rgba(255,255,255,0.06)",
        border: "1px solid rgba(255,255,255,0.12)",
        color: "rgba(255,255,255,0.7)",
        cursor: "pointer",
        fontFamily: "'DM Sans', sans-serif",
        fontSize: 15,
        fontWeight: 600,
      }}
    >
      {children}
    </button>
  )
}

function InputField({ label, value, onChange, placeholder, mono, autoUppercase, style }) {
  const [focused, setFocused] = useState(false)
  return (
    <div>
      {label && (
        <p style={{ fontSize: 11, color: "rgba(255,255,255,0.35)", margin: "0 0 8px",
                    fontFamily: "'DM Sans', sans-serif", letterSpacing: "0.06em",
                    textTransform: "uppercase" }}>
          {label}
        </p>
      )}
      <input
        value={value}
        onChange={(e) => onChange(autoUppercase ? e.target.value.toUpperCase() : e.target.value)}
        placeholder={placeholder}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        className="w-full rounded-2xl px-4 py-4 text-white outline-none transition-all"
        style={{
          background: "rgba(255,255,255,0.05)",
          border: `1.5px solid ${focused ? "#E8500A" : "rgba(255,255,255,0.08)"}`,
          fontFamily: mono ? "'DM Mono', monospace" : "'DM Sans', sans-serif",
          fontSize: 15,
          color: value ? "#fff" : undefined,
          boxSizing: "border-box",
          ...style,
        }}
        autoComplete="off"
        spellCheck={false}
      />
    </div>
  )
}

// ── STEP 1 — Vehicle + Party ──────────────────────────────────────
function Step1({ onNext, onBack }) {
  const [vehicleNo, setVehicleNo] = useState("")
  const [party, setParty]         = useState("")
  const [err, setErr]             = useState(false)

  function handleNext() {
    if (!vehicleNo.trim()) { setErr(true); return }
    onNext(vehicleNo.trim(), party.trim())
  }

  return (
    <div className="flex flex-col flex-1 px-5 pt-5 gap-6">
      <div className="flex flex-col gap-1">
        <h1 style={{ fontSize: 17, fontWeight: 600, color: "#fff", margin: 0,
                     fontFamily: "'DM Sans', sans-serif" }}>
          Nayi Delivery
        </h1>
        <p style={{ fontSize: 12, color: "rgba(255,255,255,0.35)", margin: 0,
                    fontFamily: "'DM Sans', sans-serif" }}>
          Step 1 of 3 — Vehicle aur party
        </p>
      </div>

      <div className="flex flex-col gap-4">
        <div>
          <InputField
            label="Vehicle Number"
            value={vehicleNo}
            onChange={(v) => { setVehicleNo(v); setErr(false) }}
            placeholder="HR 55 AB 1234"
            mono
            autoUppercase
          />
          {err && (
            <p style={{ fontSize: 12, color: "#F87171", margin: "6px 0 0",
                        fontFamily: "'DM Sans', sans-serif" }}>
              Vehicle number daalo pehle
            </p>
          )}
        </div>

        <InputField
          label="Party Name (optional)"
          value={party}
          onChange={setParty}
          placeholder="Buyer ka naam"
        />
      </div>

      <div className="mt-auto pb-8">
        <OrangeBtn onClick={handleNext}>Aage Badhein →</OrangeBtn>
      </div>
    </div>
  )
}

// ── STEP 2 — Product search + item list ──────────────────────────
function Step2({ vehicleNo, party, onNext, onBack }) {
  const [allProducts, setAllProducts] = useState([])
  const [query, setQuery]             = useState("")
  const [suggestions, setSuggestions] = useState([])
  const [showDrop, setShowDrop]       = useState(false)
  const [items, setItems]             = useState([])   // {product, qty}
  const [loadingProd, setLoadingProd] = useState(true)
  const dropRef  = useRef(null)
  const inputRef = useRef(null)

  // Fetch all products once
  useEffect(() => {
    api.products()
      .then((data) => { setAllProducts(data); setLoadingProd(false) })
      .catch(() => setLoadingProd(false))
  }, [])

  // Filter as user types
  useEffect(() => {
    const q = query.trim().toLowerCase()
    if (q.length < 2) { setSuggestions([]); setShowDrop(false); return }

    const matches = allProducts.filter((p) => {
      const haystack = `${p.brand} ${p.spec} ${p.type_} ${p.category}`.toLowerCase()
      return q.split(" ").every((word) => haystack.includes(word))
    }).slice(0, 8)

    setSuggestions(matches)
    setShowDrop(true)
  }, [query, allProducts])

  // Close dropdown on outside click
  useEffect(() => {
    function handler(e) {
      if (dropRef.current && !dropRef.current.contains(e.target) &&
          inputRef.current && !inputRef.current.contains(e.target)) {
        setShowDrop(false)
      }
    }
    document.addEventListener("mousedown", handler)
    return () => document.removeEventListener("mousedown", handler)
  }, [])

  function addProduct(product) {
    setQuery("")
    setShowDrop(false)
    // If already in list, just bump qty
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
        .map((i) =>
          i.product.product_id === productId ? { ...i, qty: i.qty + delta } : i
        )
        .filter((i) => i.qty > 0)
    )
  }

  const canProceed = items.length > 0
  const hasOverflow = items.some((i) => i.qty > (i.product.quantity || 0))

  return (
    <div className="flex flex-col flex-1 px-5 pt-5 gap-4">
      <div className="flex flex-col gap-1">
        <h1 style={{ fontSize: 17, fontWeight: 600, color: "#fff", margin: 0,
                     fontFamily: "'DM Sans', sans-serif" }}>
          Maal chunno
        </h1>
        <p style={{ fontSize: 12, color: "rgba(255,255,255,0.35)", margin: 0,
                    fontFamily: "'DM Sans', sans-serif" }}>
          Step 2 of 3 — {vehicleNo}
          {party ? ` → ${party}` : ""}
        </p>
      </div>

      {/* Search input + dropdown */}
      <div className="relative" ref={dropRef}>
        <div className="relative">
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onFocus={() => query.length >= 2 && setShowDrop(true)}
            placeholder={loadingProd ? "Products load ho rahe hain..." : "Product ka naam type karo..."}
            disabled={loadingProd}
            className="w-full rounded-2xl px-4 py-4 text-white outline-none"
            style={{
              background: "rgba(255,255,255,0.05)",
              border: "1.5px solid rgba(255,255,255,0.08)",
              fontFamily: "'DM Sans', sans-serif",
              fontSize: 15,
              boxSizing: "border-box",
            }}
            autoComplete="off"
          />
          {query.length > 0 && (
            <button
              onClick={() => { setQuery(""); setShowDrop(false) }}
              className="absolute right-4 top-1/2 -translate-y-1/2"
              style={{ background: "none", border: "none", color: "rgba(255,255,255,0.3)",
                       cursor: "pointer", padding: 0 }}
            >
              ✕
            </button>
          )}
        </div>

        {/* Dropdown */}
        {showDrop && suggestions.length > 0 && (
          <div
            className="absolute left-0 right-0 z-50 rounded-2xl overflow-hidden"
            style={{
              top: "calc(100% + 8px)",
              background: "#16161E",
              border: "1px solid rgba(255,255,255,0.1)",
              boxShadow: "0 20px 40px rgba(0,0,0,0.6)",
              maxHeight: 280,
              overflowY: "auto",
            }}
          >
            {suggestions.map((p) => {
              const alreadyAdded = items.some((i) => i.product.product_id === p.product_id)
              return (
                <button
                  key={p.product_id}
                  onClick={() => addProduct(p)}
                  className="w-full flex items-center gap-3 px-4 py-3 text-left transition-colors"
                  style={{
                    background: alreadyAdded ? "rgba(232,80,10,0.08)" : "transparent",
                    border: "none",
                    borderBottom: "1px solid rgba(255,255,255,0.05)",
                    cursor: "pointer",
                  }}
                >
                  <span style={{ fontSize: 20, flexShrink: 0 }}>
                    {CAT_EMOJI[p.category] || "📦"}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="truncate" style={{ margin: 0, fontSize: 13, fontWeight: 600,
                                                     color: "#fff", fontFamily: "'DM Sans', sans-serif" }}>
                      {p.brand}
                      {p.spec ? ` · ${p.spec}` : ""}
                      {p.type_ ? ` ${p.type_}` : ""}
                    </p>
                    <p style={{ margin: 0, fontSize: 11, color: "rgba(255,255,255,0.35)",
                                fontFamily: "'DM Mono', monospace" }}>
                      {p.quantity ?? 0} {p.unit || "nos"} in stock
                    </p>
                  </div>
                  {alreadyAdded && (
                    <span style={{ fontSize: 10, color: "#E8500A", flexShrink: 0,
                                   fontFamily: "'DM Sans', sans-serif" }}>
                      Added
                    </span>
                  )}
                </button>
              )
            })}
          </div>
        )}
        {showDrop && suggestions.length === 0 && query.length >= 2 && (
          <div
            className="absolute left-0 right-0 z-50 rounded-2xl px-4 py-5 text-center"
            style={{
              top: "calc(100% + 8px)",
              background: "#16161E",
              border: "1px solid rgba(255,255,255,0.1)",
              fontSize: 13,
              color: "rgba(255,255,255,0.35)",
              fontFamily: "'DM Sans', sans-serif",
            }}
          >
            Koi match nahi mila
          </div>
        )}
      </div>

      {/* Added items list */}
      {items.length === 0 ? (
        <div
          className="flex-1 flex flex-col items-center justify-center gap-2"
          style={{ color: "rgba(255,255,255,0.2)" }}
        >
          <span style={{ fontSize: 40 }}>📦</span>
          <p style={{ fontSize: 13, fontFamily: "'DM Sans', sans-serif", margin: 0 }}>
            Upar search karo aur product chunno
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-2 flex-1 overflow-y-auto pb-2">
          {items.map(({ product, qty }) => {
            const overflow = qty > (product.quantity || 0)
            return (
              <div
                key={product.product_id}
                className="flex items-center gap-3 px-4 py-3 rounded-2xl"
                style={{
                  background: overflow ? "rgba(248,113,113,0.08)" : "rgba(255,255,255,0.05)",
                  border: `1px solid ${overflow ? "rgba(248,113,113,0.35)" : "rgba(255,255,255,0.08)"}`,
                }}
              >
                <span style={{ fontSize: 18, flexShrink: 0 }}>
                  {CAT_EMOJI[product.category] || "📦"}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="truncate" style={{ margin: 0, fontSize: 13, fontWeight: 600,
                                                   color: "#fff", fontFamily: "'DM Sans', sans-serif" }}>
                    {product.brand}
                    {product.spec ? ` ${product.spec}` : ""}
                    {product.type_ ? ` ${product.type_}` : ""}
                  </p>
                  {overflow && (
                    <p style={{ margin: "2px 0 0", fontSize: 11, color: "#F87171",
                                fontFamily: "'DM Sans', sans-serif" }}>
                      Sirf {product.quantity} available hai
                    </p>
                  )}
                </div>

                {/* Qty controls */}
                <div className="flex items-center gap-2 flex-shrink-0">
                  <button
                    onClick={() => changeQty(product.product_id, -1)}
                    className="w-8 h-8 rounded-xl flex items-center justify-center transition-opacity active:opacity-60"
                    style={{ background: "rgba(255,255,255,0.1)", border: "none",
                             cursor: "pointer", color: "rgba(255,255,255,0.7)", fontSize: 18 }}
                  >
                    −
                  </button>
                  <span style={{ minWidth: 28, textAlign: "center", fontSize: 15,
                                 fontWeight: 600, color: "#fff",
                                 fontFamily: "'DM Mono', monospace" }}>
                    {qty}
                  </span>
                  <button
                    onClick={() => changeQty(product.product_id, 1)}
                    className="w-8 h-8 rounded-xl flex items-center justify-center transition-opacity active:opacity-60"
                    style={{ background: "#E8500A", border: "none", cursor: "pointer",
                             color: "#fff", fontSize: 18 }}
                  >
                    +
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Bottom CTA */}
      <div className="pb-8 flex flex-col gap-2">
        {hasOverflow && (
          <p style={{ fontSize: 12, color: "#FACC15", textAlign: "center",
                      fontFamily: "'DM Sans', sans-serif", margin: 0 }}>
            ⚠️ Kuch items ki quantity available stock se zyada hai
          </p>
        )}
        <OrangeBtn
          onClick={() => onNext(items)}
          disabled={!canProceed || hasOverflow}
        >
          Challan Banao →
        </OrangeBtn>
      </div>
    </div>
  )
}

// ── STEP 3 — Confirm + submit ─────────────────────────────────────
function Step3({ vehicleNo, party, items, onBack }) {
  const navigate = useNavigate()
  const [loading, setLoading]   = useState(false)
  const [errors, setErrors]     = useState([])
  const [success, setSuccess]   = useState(false)
  const [pdfUrl, setPdfUrl]     = useState(null)

  const totalQty = items.reduce((sum, { qty }) => sum + qty, 0)

  async function handleConfirm() {
    setLoading(true)
    setErrors([])

    try {
      // 1. Deduct stock
      const stockRes = await fetch(`${BASE}/api/stock/out`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          vehicle_no: vehicleNo,
          party,
          operator: "Frontend",
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

      const stockData = await stockRes.json()

      if (!stockRes.ok) {
        setErrors([stockData.detail || "Stock update fail hua"])
        setLoading(false)
        return
      }

      // Collect API-level errors (partial failures)
      const apiErrors = stockData.errors || []

      // 2. Generate PDF
      const pdfRes = await fetch(`${BASE}/api/challan/pdf`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          vehicle_no: vehicleNo,
          operator:   "Swayam",
          party,
          items: items.map(({ product, qty }) => ({
            brand:    product.brand,
            spec:     product.spec  || "",
            type:     product.type_ || "",
            quantity: qty,
            unit:     product.unit  || "nos",
          })),
        }),
      })

      if (pdfRes.ok) {
        const blob = await pdfRes.blob()
        const url  = URL.createObjectURL(blob)
        setPdfUrl(url)
        window.open(url, "_blank")
      } else {
        apiErrors.push("PDF generate nahi hua — stock deduct ho gaya")
      }

      if (apiErrors.length > 0) {
        setErrors(apiErrors)
      }

      setSuccess(true)

    } catch (err) {
      setErrors([`Network error: ${err.message}`])
    } finally {
      setLoading(false)
    }
  }

  // ── Success screen ────────────────────────────────────────────
  if (success) {
    return (
      <div className="flex flex-col flex-1 items-center justify-center px-5 gap-6">
        {/* Animated checkmark */}
        <div
          className="flex items-center justify-center rounded-full"
          style={{
            width: 80, height: 80,
            backgroundColor: "rgba(52,211,153,0.15)",
            border: "2px solid rgba(52,211,153,0.4)",
            animation: "pop 0.4s cubic-bezier(0.34,1.56,0.64,1) both",
          }}
        >
          <svg width="36" height="36" viewBox="0 0 24 24" fill="none"
               stroke="#34D399" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="20 6 9 17 4 12" />
          </svg>
        </div>

        <div className="text-center flex flex-col gap-2">
          <p style={{ fontSize: 20, fontWeight: 700, color: "#fff", margin: 0,
                      fontFamily: "'DM Sans', sans-serif" }}>
            Challan ban gaya! 🎉
          </p>
          <p style={{ fontSize: 13, color: "rgba(255,255,255,0.4)", margin: 0,
                      fontFamily: "'DM Sans', sans-serif" }}>
            Stock updated for
          </p>
          <p style={{ fontSize: 22, fontWeight: 700, color: "#E8500A", margin: 0,
                      fontFamily: "'DM Mono', monospace", letterSpacing: "0.05em" }}>
            {vehicleNo}
          </p>
          {party && (
            <p style={{ fontSize: 13, color: "rgba(255,255,255,0.5)", margin: 0,
                        fontFamily: "'DM Sans', sans-serif" }}>
              → {party}
            </p>
          )}
        </div>

        {/* Show any partial errors */}
        {errors.length > 0 && (
          <div
            className="w-full rounded-2xl px-4 py-3"
            style={{ background: "rgba(248,113,113,0.1)", border: "1px solid rgba(248,113,113,0.25)" }}
          >
            <p style={{ fontSize: 12, color: "#F87171", fontFamily: "'DM Sans', sans-serif", margin: 0 }}>
              ⚠️ Kuch items fail hue:
            </p>
            {errors.map((e, i) => (
              <p key={i} style={{ fontSize: 12, color: "#F87171",
                                  fontFamily: "'DM Sans', sans-serif", margin: "4px 0 0" }}>
                • {e}
              </p>
            ))}
          </div>
        )}

        <div className="w-full flex flex-col gap-3 mt-4">
          {pdfUrl && (
            <GhostBtn onClick={() => window.open(pdfUrl, "_blank")}>
              📄 PDF dobara dekho
            </GhostBtn>
          )}
          <OrangeBtn onClick={() => navigate("/home")}>
            Naya Challan
          </OrangeBtn>
        </div>

        <style>{`
          @keyframes pop {
            from { transform: scale(0.5); opacity: 0; }
            to   { transform: scale(1);   opacity: 1; }
          }
        `}</style>
      </div>
    )
  }

  // ── Confirm summary screen ────────────────────────────────────
  return (
    <div className="flex flex-col flex-1 px-5 pt-5 gap-5">
      <div className="flex flex-col gap-1">
        <h1 style={{ fontSize: 17, fontWeight: 600, color: "#fff", margin: 0,
                     fontFamily: "'DM Sans', sans-serif" }}>
          Confirm karo
        </h1>
        <p style={{ fontSize: 12, color: "rgba(255,255,255,0.35)", margin: 0,
                    fontFamily: "'DM Sans', sans-serif" }}>
          Step 3 of 3 — review aur submit
        </p>
      </div>

      {/* Vehicle + party badge */}
      <div
        className="rounded-2xl px-4 py-4 flex flex-col gap-1"
        style={{ background: "rgba(232,80,10,0.1)", border: "1px solid rgba(232,80,10,0.25)" }}
      >
        <p style={{ fontSize: 11, color: "rgba(255,255,255,0.35)", margin: 0,
                    fontFamily: "'DM Sans', sans-serif", textTransform: "uppercase",
                    letterSpacing: "0.08em" }}>
          Vehicle
        </p>
        <p style={{ fontSize: 22, fontWeight: 700, color: "#E8500A", margin: 0,
                    fontFamily: "'DM Mono', monospace", letterSpacing: "0.08em" }}>
          {vehicleNo}
        </p>
        {party && (
          <p style={{ fontSize: 13, color: "rgba(255,255,255,0.55)", margin: "2px 0 0",
                      fontFamily: "'DM Sans', sans-serif" }}>
            → {party}
          </p>
        )}
      </div>

      {/* Items list */}
      <div className="flex flex-col gap-2 flex-1 overflow-y-auto">
        {items.map(({ product, qty }) => (
          <div
            key={product.product_id}
            className="flex items-center gap-3 px-4 py-3 rounded-2xl"
            style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.07)" }}
          >
            <span style={{ fontSize: 18, flexShrink: 0 }}>
              {CAT_EMOJI[product.category] || "📦"}
            </span>
            <div className="flex-1 min-w-0">
              <p className="truncate" style={{ margin: 0, fontSize: 13, fontWeight: 600,
                                               color: "#fff", fontFamily: "'DM Sans', sans-serif" }}>
                {product.brand}
                {product.spec ? ` ${product.spec}` : ""}
                {product.type_ ? ` ${product.type_}` : ""}
              </p>
              <p style={{ margin: 0, fontSize: 11, color: "rgba(255,255,255,0.35)",
                          fontFamily: "'DM Mono', monospace" }}>
                {product.unit || "nos"}
              </p>
            </div>
            <span style={{ fontSize: 17, fontWeight: 700, color: "#fff",
                           fontFamily: "'DM Mono', monospace", flexShrink: 0 }}>
              ×{qty}
            </span>
          </div>
        ))}
      </div>

      {/* Total */}
      <div
        className="rounded-2xl px-4 py-3 flex items-center justify-between"
        style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.07)" }}
      >
        <span style={{ fontSize: 13, color: "rgba(255,255,255,0.5)",
                       fontFamily: "'DM Sans', sans-serif" }}>
          Total items
        </span>
        <span style={{ fontSize: 17, fontWeight: 700, color: "#fff",
                       fontFamily: "'DM Mono', monospace" }}>
          {totalQty} units
        </span>
      </div>

      {/* Errors */}
      {errors.length > 0 && (
        <div
          className="rounded-2xl px-4 py-3"
          style={{ background: "rgba(248,113,113,0.1)", border: "1px solid rgba(248,113,113,0.3)" }}
        >
          {errors.map((e, i) => (
            <p key={i} style={{ margin: i === 0 ? 0 : "4px 0 0", fontSize: 13,
                                color: "#F87171", fontFamily: "'DM Sans', sans-serif" }}>
              ❌ {e}
            </p>
          ))}
        </div>
      )}

      {/* Actions */}
      <div className="pb-8 flex flex-col gap-3">
        <GhostBtn onClick={onBack}>← Wapas Jao</GhostBtn>
        <OrangeBtn onClick={handleConfirm} loading={loading}>
          {loading ? "Processing..." : "Confirm aur PDF Banao ✓"}
        </OrangeBtn>
      </div>
    </div>
  )
}


// ── Main Challan page (step controller) ───────────────────────────
export default function Challan() {
  const navigate = useNavigate()
  const [step, setStep]           = useState(1)
  const [vehicleNo, setVehicleNo] = useState("")
  const [party, setParty]         = useState("")
  const [items, setItems]         = useState([])

  // Auth guard
  useEffect(() => {
    if (!localStorage.getItem("auth")) navigate("/login", { replace: true })
  }, [navigate])

  const stepLabel = ["", "Vehicle Details", "Products", "Confirm"][step]

  return (
    <div
      className="min-h-dvh flex flex-col"
      style={{ backgroundColor: "#0A0A0F", fontFamily: "'DM Sans', sans-serif" }}
    >
      {/* Header */}
      <div className="flex items-center gap-3 px-5 pt-14 pb-4">
        <BackArrow onClick={() => (step === 1 ? navigate("/home") : setStep((s) => s - 1))} />
        <div className="flex-1">
          <p style={{ fontSize: 11, color: "rgba(255,255,255,0.3)", margin: 0,
                      textTransform: "uppercase", letterSpacing: "0.1em",
                      fontFamily: "'DM Sans', sans-serif" }}>
            Delivery Challan
          </p>
        </div>
        {/* Step pills */}
        <div className="flex gap-1.5">
          {[1, 2, 3].map((s) => (
            <span
              key={s}
              className="rounded-full"
              style={{
                width: s === step ? 20 : 6,
                height: 6,
                backgroundColor: s === step ? "#E8500A" : s < step
                  ? "rgba(232,80,10,0.4)"
                  : "rgba(255,255,255,0.15)",
                transition: "all 0.3s ease",
              }}
            />
          ))}
        </div>
      </div>

      {/* Step content */}
      {step === 1 && (
        <Step1
          onNext={(v, p) => { setVehicleNo(v); setParty(p); setStep(2) }}
          onBack={() => navigate("/home")}
        />
      )}
      {step === 2 && (
        <Step2
          vehicleNo={vehicleNo}
          party={party}
          onNext={(selectedItems) => { setItems(selectedItems); setStep(3) }}
          onBack={() => setStep(1)}
        />
      )}
      {step === 3 && (
        <Step3
          vehicleNo={vehicleNo}
          party={party}
          items={items}
          onBack={() => setStep(2)}
        />
      )}
    </div>
  )
}
