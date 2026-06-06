import { useEffect, useRef, useState } from "react"
import { useNavigate } from "react-router-dom"

const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000"

const TYPE_OPTIONS  = ["", "DCR", "N-DCR", "1P", "3P", "Mono", "Other"]
const UNIT_OPTIONS  = ["nos", "meters", "sets", "pcs"]

const CAT_EMOJI = {
  "Solar Panel": "☀️", "Inverter": "⚡", "ACDB/DCDB": "🔌",
  "Cable": "🔗", "PVC Material": "🧱", "Structure": "🏗️",
}

// ── Shared UI ────────────────────────────────────────────────────
function BackBtn({ onClick }) {
  return (
    <button onClick={onClick} style={{
      width: 36, height: 36, borderRadius: 12,
      background: "rgba(255,255,255,0.07)", border: "none", cursor: "pointer",
      display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
    }}>
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
           stroke="rgba(255,255,255,0.8)" strokeWidth="2.2"
           strokeLinecap="round" strokeLinejoin="round">
        <polyline points="15 18 9 12 15 6" />
      </svg>
    </button>
  )
}

function OrangeBtn({ children, onClick, disabled, loading, fullWidth = true }) {
  return (
    <button onClick={onClick} disabled={disabled || loading} style={{
      width: fullWidth ? "100%" : "auto",
      borderRadius: 18, padding: "14px 24px",
      backgroundColor: disabled || loading ? "rgba(232,80,10,0.35)" : "#E8500A",
      border: "none", cursor: disabled || loading ? "not-allowed" : "pointer",
      fontFamily: "'DM Sans', sans-serif", fontSize: 15, fontWeight: 600,
      color: "#fff", transition: "all 0.2s",
    }}>
      {loading ? "..." : children}
    </button>
  )
}

function Label({ children }) {
  return (
    <p style={{
      fontSize: 11, color: "rgba(255,255,255,0.35)", margin: "0 0 6px",
      textTransform: "uppercase", letterSpacing: "0.08em",
      fontFamily: "'DM Sans', sans-serif",
    }}>{children}</p>
  )
}

function NewBadge() {
  return (
    <span style={{
      fontSize: 10, fontWeight: 700, padding: "2px 8px", borderRadius: 20,
      backgroundColor: "rgba(232,80,10,0.2)", color: "#E8500A",
      border: "1px solid rgba(232,80,10,0.4)",
      fontFamily: "'DM Sans', sans-serif", letterSpacing: "0.05em",
    }}>
      NAYA BANEGA
    </span>
  )
}

// Combobox: dropdown + free-text fallback
function Combobox({ label, value, onChange, options, placeholder, isNew }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    function h(e) { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener("mousedown", h)
    return () => document.removeEventListener("mousedown", h)
  }, [])

  const filtered = options.filter(o =>
    o.name.toLowerCase().includes(value.toLowerCase())
  )

  return (
    <div ref={ref}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
        <Label>{label}</Label>
        {isNew && value && <NewBadge />}
      </div>
      <div style={{ position: "relative" }}>
        <input
          value={value}
          onChange={e => { onChange(e.target.value); setOpen(true) }}
          onFocus={() => setOpen(true)}
          placeholder={placeholder}
          style={{
            width: "100%", borderRadius: 16,
            padding: "13px 16px", background: "rgba(255,255,255,0.05)",
            border: "1.5px solid rgba(255,255,255,0.1)", color: "#fff",
            fontFamily: "'DM Sans', sans-serif", fontSize: 14,
            boxSizing: "border-box", outline: "none",
          }}
        />
        {open && (options.length > 0) && (
          <div style={{
            position: "absolute", left: 0, right: 0, top: "calc(100% + 6px)",
            zIndex: 50, background: "#16161E",
            border: "1px solid rgba(255,255,255,0.1)", borderRadius: 16,
            overflow: "hidden", maxHeight: 200, overflowY: "auto",
            boxShadow: "0 16px 40px rgba(0,0,0,0.6)",
          }}>
            {filtered.map((o, i) => (
              <button key={o.id || i}
                onClick={() => { onChange(o.name); setOpen(false) }}
                style={{
                  width: "100%", padding: "11px 16px", textAlign: "left",
                  background: "transparent", border: "none", cursor: "pointer",
                  borderBottom: i < filtered.length - 1 ? "1px solid rgba(255,255,255,0.05)" : "none",
                  color: "#fff", fontFamily: "'DM Sans', sans-serif", fontSize: 13,
                }}
              >
                {CAT_EMOJI[o.name] || ""} {o.name}
              </button>
            ))}
            {value && !options.find(o => o.name.toLowerCase() === value.toLowerCase()) && (
              <button
                onClick={() => { onChange(value); setOpen(false) }}
                style={{
                  width: "100%", padding: "11px 16px", textAlign: "left",
                  background: "rgba(232,80,10,0.1)", border: "none", cursor: "pointer",
                  color: "#E8500A", fontFamily: "'DM Sans', sans-serif", fontSize: 13,
                  fontWeight: 600,
                }}
              >
                + "{value}" naya banega
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function SelectField({ label, value, onChange, options }) {
  return (
    <div>
      <Label>{label}</Label>
      <select
        value={value}
        onChange={e => onChange(e.target.value)}
        style={{
          width: "100%", borderRadius: 16,
          padding: "13px 16px", background: "rgba(255,255,255,0.05)",
          border: "1.5px solid rgba(255,255,255,0.1)", color: value ? "#fff" : "rgba(255,255,255,0.35)",
          fontFamily: "'DM Sans', sans-serif", fontSize: 14, outline: "none",
          boxSizing: "border-box", appearance: "none",
          backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='rgba(255,255,255,0.4)' stroke-width='2'%3E%3Cpolyline points='6 9 12 15 18 9'/%3E%3C/svg%3E")`,
          backgroundRepeat: "no-repeat", backgroundPosition: "right 16px center",
        }}
      >
        {options.map(o => (
          <option key={o} value={o}
            style={{ background: "#1a1a24", color: "#fff" }}>
            {o || "— Select —"}
          </option>
        ))}
      </select>
    </div>
  )
}


// ── STEP 1 — Free text ───────────────────────────────────────────
function Step1({ onParsed }) {
  const [text, setText]       = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState(null)

  async function handleParse() {
    if (!text.trim()) return
    setLoading(true); setError(null)
    try {
      const res  = await fetch(`${BASE}/api/parse/product`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text.trim() }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || "Parse failed")
      onParsed(data, text)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const suggestions = [
    "Nexus Solar 540W DCR panel",
    "GI Structure 2kw mounting set",
    "Polycab 5kw 3P inverter",
    "Havells DC cable 500 meters",
  ]

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 20 }}>
      <div>
        <p style={{ fontSize: 17, fontWeight: 600, color: "#fff", margin: "0 0 4px",
                    fontFamily: "'DM Sans', sans-serif" }}>
          Naya product kya hai?
        </p>
        <p style={{ fontSize: 12, color: "rgba(255,255,255,0.35)", margin: 0,
                    fontFamily: "'DM Sans', sans-serif" }}>
          Natural language mein likho — AI samjhega
        </p>
      </div>

      {/* Large textarea */}
      <textarea
        value={text}
        onChange={e => { setText(e.target.value); setError(null) }}
        placeholder={"Jaise: Waaree 650W DCR panel, ya\nGI Structure 2kw mounting set"}
        rows={5}
        style={{
          width: "100%", borderRadius: 20,
          padding: "16px", resize: "none",
          background: "rgba(255,255,255,0.05)",
          border: `1.5px solid ${text ? "rgba(232,80,10,0.5)" : "rgba(255,255,255,0.08)"}`,
          color: "#fff", fontFamily: "'DM Sans', sans-serif", fontSize: 16,
          outline: "none", boxSizing: "border-box", lineHeight: 1.5,
          transition: "border-color 0.2s",
        }}
      />

      {/* Quick suggestions */}
      <div>
        <p style={{ fontSize: 11, color: "rgba(255,255,255,0.25)", margin: "0 0 8px",
                    textTransform: "uppercase", letterSpacing: "0.08em" }}>
          Examples
        </p>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          {suggestions.map(s => (
            <button key={s} onClick={() => setText(s)} style={{
              padding: "6px 12px", borderRadius: 20,
              background: "rgba(255,255,255,0.06)",
              border: "1px solid rgba(255,255,255,0.1)",
              color: "rgba(255,255,255,0.55)",
              cursor: "pointer", fontSize: 12,
              fontFamily: "'DM Sans', sans-serif",
            }}>{s}</button>
          ))}
        </div>
      </div>

      {error && (
        <p style={{ fontSize: 13, color: "#F87171", margin: 0,
                    fontFamily: "'DM Sans', sans-serif" }}>
          ❌ {error}
        </p>
      )}

      <div style={{ marginTop: "auto" }}>
        <OrangeBtn onClick={handleParse} disabled={!text.trim()} loading={loading}>
          {loading ? "AI soch raha hai..." : "Samjho ✨"}
        </OrangeBtn>
      </div>
    </div>
  )
}


// ── STEP 2 — Confirm + edit ──────────────────────────────────────
function Step2({ parsed, onSave, onBack }) {
  const [categories, setCategories] = useState([])
  const [brands, setBrands]         = useState([])

  const [category, setCategory] = useState(parsed.category || "")
  const [brand, setBrand]       = useState(parsed.brand    || "")
  const [spec, setSpec]         = useState(parsed.spec     || "")
  const [type_, setType]        = useState(parsed.type     || "")
  const [unit, setUnit]         = useState(parsed.unit     || "nos")
  const [quantity, setQuantity] = useState(parsed.quantity || 0)

  useEffect(() => {
    Promise.all([
      fetch(`${BASE}/api/categories`).then(r => r.json()),
      fetch(`${BASE}/api/brands`).then(r => r.json()),
    ]).then(([cats, brands]) => {
      setCategories(cats)
      setBrands(brands)
    }).catch(console.error)
  }, [])

  const isNewCategory = category &&
    !categories.find(c => c.name.toLowerCase() === category.toLowerCase())
  const isNewBrand = brand &&
    !brands.find(b => b.name.toLowerCase() === brand.toLowerCase())

  function handleSave() {
    onSave({ category, brand, spec, type_, unit, quantity: Number(quantity) },
            isNewCategory, isNewBrand)
  }

  const canSave = category.trim() && brand.trim()

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 16 }}>
      <div>
        <p style={{ fontSize: 17, fontWeight: 600, color: "#fff", margin: "0 0 4px",
                    fontFamily: "'DM Sans', sans-serif" }}>
          Check karo aur edit karo
        </p>
        <p style={{ fontSize: 12, color: "rgba(255,255,255,0.35)", margin: 0,
                    fontFamily: "'DM Sans', sans-serif" }}>
          AI ne yeh samjha — galat ho toh theek karo
        </p>
      </div>

      {/* AI parsed preview chip */}
      <div style={{
        padding: "10px 14px", borderRadius: 14,
        background: "rgba(232,80,10,0.08)",
        border: "1px solid rgba(232,80,10,0.2)",
        fontSize: 12, color: "rgba(255,255,255,0.5)",
        fontFamily: "'DM Sans', sans-serif",
      }}>
        ✨ AI parsed: <span style={{ color: "#E8500A", fontWeight: 600 }}>
          {[parsed.brand, parsed.spec, parsed.type, parsed.category].filter(Boolean).join(" · ")}
        </span>
      </div>

      {/* Fields */}
      <Combobox
        label="Category"
        value={category}
        onChange={setCategory}
        options={categories}
        placeholder="Solar Panel, Inverter..."
        isNew={isNewCategory}
      />

      <Combobox
        label="Brand"
        value={brand}
        onChange={setBrand}
        options={brands}
        placeholder="Brand ka naam"
        isNew={isNewBrand}
      />

      <div>
        <Label>Spec / Size</Label>
        <input
          value={spec}
          onChange={e => setSpec(e.target.value)}
          placeholder="e.g. 650, 3kw, 150X50"
          style={{
            width: "100%", borderRadius: 16, padding: "13px 16px",
            background: "rgba(255,255,255,0.05)",
            border: "1.5px solid rgba(255,255,255,0.1)",
            color: "#fff", fontFamily: "'DM Sans', sans-serif",
            fontSize: 14, outline: "none", boxSizing: "border-box",
          }}
        />
      </div>

      <SelectField
        label="Type / Variant"
        value={type_}
        onChange={setType}
        options={TYPE_OPTIONS}
      />

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        <SelectField
          label="Unit"
          value={unit}
          onChange={setUnit}
          options={UNIT_OPTIONS}
        />
        <div>
          <Label>Initial Qty</Label>
          <input
            type="number"
            min={0}
            value={quantity}
            onChange={e => setQuantity(e.target.value)}
            style={{
              width: "100%", borderRadius: 16, padding: "13px 16px",
              background: "rgba(255,255,255,0.05)",
              border: "1.5px solid rgba(255,255,255,0.1)",
              color: "#fff", fontFamily: "'DM Mono', monospace",
              fontSize: 14, outline: "none", boxSizing: "border-box",
            }}
          />
        </div>
      </div>

      {/* New entity warnings */}
      {(isNewCategory || isNewBrand) && (
        <div style={{
          padding: "12px 14px", borderRadius: 14,
          background: "rgba(250,204,21,0.07)",
          border: "1px solid rgba(250,204,21,0.2)",
        }}>
          <p style={{ margin: 0, fontSize: 12, color: "#FACC15",
                      fontFamily: "'DM Sans', sans-serif" }}>
            ⚠️ Yeh save hoga:
          </p>
          {isNewCategory && (
            <p style={{ margin: "4px 0 0", fontSize: 12, color: "rgba(255,255,255,0.5)" }}>
              • Naya category: <strong style={{ color: "#fff" }}>{category}</strong>
            </p>
          )}
          {isNewBrand && (
            <p style={{ margin: "4px 0 0", fontSize: 12, color: "rgba(255,255,255,0.5)" }}>
              • Naya brand: <strong style={{ color: "#fff" }}>{brand}</strong>
            </p>
          )}
        </div>
      )}

      <div style={{ display: "flex", gap: 12, marginTop: "auto", paddingBottom: 8 }}>
        <button onClick={onBack} style={{
          flex: 1, borderRadius: 18, padding: "14px",
          background: "rgba(255,255,255,0.06)",
          border: "1px solid rgba(255,255,255,0.1)",
          color: "rgba(255,255,255,0.7)", cursor: "pointer",
          fontFamily: "'DM Sans', sans-serif", fontSize: 15, fontWeight: 600,
        }}>
          ← Wapas
        </button>
        <button onClick={handleSave} disabled={!canSave} style={{
          flex: 2, borderRadius: 18, padding: "14px",
          backgroundColor: !canSave ? "rgba(232,80,10,0.35)" : "#E8500A",
          border: "none", cursor: !canSave ? "not-allowed" : "pointer",
          color: "#fff", fontFamily: "'DM Sans', sans-serif",
          fontSize: 15, fontWeight: 600,
        }}>
          Save karo ✓
        </button>
      </div>
    </div>
  )
}


// ── STEP 3 — Saving + success ────────────────────────────────────
function Step3({ fields, isNewCategory, isNewBrand }) {
  const navigate = useNavigate()
  const [status, setStatus]   = useState("saving") // saving | success | error
  const [result, setResult]   = useState(null)
  const [errors, setErrors]   = useState([])

  useEffect(() => {
    (async () => {
      const errs = []

      // 1. Create category if new
      if (isNewCategory) {
        const r = await fetch(`${BASE}/api/categories`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name: fields.category }),
        })
        if (!r.ok) errs.push(`Category create failed: ${(await r.json()).detail}`)
      }

      // 2. Create brand if new
      if (isNewBrand) {
        const r = await fetch(`${BASE}/api/brands`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name: fields.brand }),
        })
        if (!r.ok) errs.push(`Brand create failed: ${(await r.json()).detail}`)
      }

      // 3. Add product
      const r = await fetch(`${BASE}/api/products/add`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          category: fields.category,
          brand:    fields.brand,
          spec:     fields.spec,
          type_:    fields.type_,
          unit:     fields.unit,
          quantity: Number(fields.quantity),
        }),
      })
      const data = await r.json()

      if (!r.ok) {
        errs.push(data.detail || "Product add failed")
        setErrors(errs)
        setStatus("error")
        return
      }

      setErrors(errs)
      setResult(data)
      setStatus("success")
    })()
  }, [])

  if (status === "saving") {
    return (
      <div style={{ flex: 1, display: "flex", flexDirection: "column",
                    alignItems: "center", justifyContent: "center", gap: 16 }}>
        <div style={{
          width: 56, height: 56, borderRadius: "50%",
          border: "3px solid rgba(232,80,10,0.2)",
          borderTopColor: "#E8500A",
          animation: "spin 0.8s linear infinite",
        }} />
        <p style={{ fontSize: 15, color: "rgba(255,255,255,0.5)",
                    fontFamily: "'DM Sans', sans-serif", margin: 0 }}>
          Save ho raha hai...
        </p>
        <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
      </div>
    )
  }

  if (status === "error") {
    return (
      <div style={{ flex: 1, display: "flex", flexDirection: "column",
                    alignItems: "center", justifyContent: "center",
                    gap: 16, padding: "0 4px" }}>
        <span style={{ fontSize: 48 }}>❌</span>
        {errors.map((e, i) => (
          <p key={i} style={{ margin: 0, fontSize: 13, color: "#F87171",
                              fontFamily: "'DM Sans', sans-serif", textAlign: "center" }}>
            {e}
          </p>
        ))}
        <OrangeBtn onClick={() => navigate("/home")}>Home Jao</OrangeBtn>
      </div>
    )
  }

  // success
  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column",
                  alignItems: "center", justifyContent: "center", gap: 20 }}>
      {/* Checkmark */}
      <div style={{
        width: 80, height: 80, borderRadius: "50%",
        backgroundColor: "rgba(52,211,153,0.15)",
        border: "2px solid rgba(52,211,153,0.4)",
        display: "flex", alignItems: "center", justifyContent: "center",
        animation: "pop 0.4s cubic-bezier(0.34,1.56,0.64,1) both",
      }}>
        <svg width="36" height="36" viewBox="0 0 24 24" fill="none"
             stroke="#34D399" strokeWidth="2.5"
             strokeLinecap="round" strokeLinejoin="round">
          <polyline points="20 6 9 17 4 12" />
        </svg>
      </div>

      <div style={{ textAlign: "center" }}>
        <p style={{ fontSize: 20, fontWeight: 700, color: "#fff", margin: "0 0 4px",
                    fontFamily: "'DM Sans', sans-serif" }}>
          Product add ho gaya! 🎉
        </p>
        <p style={{ fontSize: 13, color: "rgba(255,255,255,0.4)", margin: 0 }}>
          {CAT_EMOJI[result?.category] || "📦"} {result?.category}
        </p>
      </div>

      {/* Product card */}
      <div style={{
        width: "100%", borderRadius: 20, padding: "16px",
        background: "rgba(52,211,153,0.06)",
        border: "1px solid rgba(52,211,153,0.2)",
      }}>
        <p style={{ margin: 0, fontSize: 18, fontWeight: 700, color: "#fff",
                    fontFamily: "'DM Sans', sans-serif" }}>
          {result?.brand} {result?.spec} {result?.type_}
        </p>
        <p style={{ margin: "6px 0 0", fontSize: 12,
                    fontFamily: "'DM Mono', monospace", color: "rgba(255,255,255,0.35)" }}>
          {result?.product_id}
        </p>
        <div style={{ marginTop: 10, display: "flex", gap: 8 }}>
          <span style={{
            fontSize: 11, padding: "3px 10px", borderRadius: 20,
            background: "rgba(255,255,255,0.08)", color: "rgba(255,255,255,0.5)",
          }}>
            {result?.unit}
          </span>
          <span style={{
            fontSize: 11, padding: "3px 10px", borderRadius: 20,
            background: "rgba(255,255,255,0.08)", color: "rgba(255,255,255,0.5)",
          }}>
            Qty: {result?.quantity}
          </span>
        </div>
      </div>

      {/* Partial errors */}
      {errors.length > 0 && errors.map((e, i) => (
        <p key={i} style={{ margin: 0, fontSize: 12, color: "#FACC15",
                            fontFamily: "'DM Sans', sans-serif" }}>
          ⚠️ {e}
        </p>
      ))}

      <div style={{ width: "100%", display: "flex", flexDirection: "column", gap: 10 }}>
        <OrangeBtn onClick={() => window.location.reload()}>
          Aur Product Add Karo
        </OrangeBtn>
        <button onClick={() => navigate("/home")} style={{
          width: "100%", borderRadius: 18, padding: "14px",
          background: "rgba(255,255,255,0.06)",
          border: "1px solid rgba(255,255,255,0.1)",
          color: "rgba(255,255,255,0.7)", cursor: "pointer",
          fontFamily: "'DM Sans', sans-serif", fontSize: 15, fontWeight: 600,
        }}>
          Home Jao
        </button>
      </div>

      <style>{`
        @keyframes pop{from{transform:scale(.5);opacity:0}to{transform:scale(1);opacity:1}}
      `}</style>
    </div>
  )
}


// ── Main AddProduct page ─────────────────────────────────────────
export default function AddProduct() {
  const navigate = useNavigate()
  const [step, setStep]         = useState(1)
  const [parsed, setParsed]     = useState(null)
  const [rawText, setRawText]   = useState("")
  const [fields, setFields]     = useState(null)
  const [isNewCat, setIsNewCat] = useState(false)
  const [isNewBrand, setIsNewBrand] = useState(false)

  useEffect(() => {
    if (!localStorage.getItem("auth")) navigate("/login", { replace: true })
  }, [navigate])

  function handleParsed(data, text) {
    setParsed(data)
    setRawText(text)
    setStep(2)
  }

  function handleSave(f, newCat, newBrand) {
    setFields(f)
    setIsNewCat(newCat)
    setIsNewBrand(newBrand)
    setStep(3)
  }

  const stepLabels = ["", "Batao", "Check karo", "Save"]

  return (
    <div style={{
      minHeight: "100dvh", display: "flex", flexDirection: "column",
      backgroundColor: "#0A0A0F", fontFamily: "'DM Sans', sans-serif",
    }}>
      {/* Header */}
      <div style={{
        display: "flex", alignItems: "center", gap: 12,
        padding: "56px 20px 20px",
      }}>
        <BackBtn onClick={() => step > 1 ? setStep(s => s - 1) : navigate("/home")} />
        <div style={{ flex: 1 }}>
          <p style={{
            fontSize: 11, color: "rgba(255,255,255,0.3)", margin: 0,
            textTransform: "uppercase", letterSpacing: "0.1em",
          }}>
            Naya Product
          </p>
        </div>
        {/* Step pills */}
        <div style={{ display: "flex", gap: 6 }}>
          {[1, 2, 3].map(s => (
            <span key={s} style={{
              height: 6, borderRadius: 3,
              width: s === step ? 20 : 6,
              backgroundColor: s === step ? "#E8500A"
                : s < step ? "rgba(232,80,10,0.4)"
                : "rgba(255,255,255,0.15)",
              transition: "all 0.3s ease",
            }} />
          ))}
        </div>
      </div>

      {/* Content */}
      <div style={{ flex: 1, padding: "0 20px 32px", display: "flex", flexDirection: "column" }}>
        {step === 1 && <Step1 onParsed={handleParsed} />}
        {step === 2 && parsed && (
          <Step2
            parsed={parsed}
            onSave={handleSave}
            onBack={() => setStep(1)}
          />
        )}
        {step === 3 && fields && (
          <Step3
            fields={fields}
            isNewCategory={isNewCat}
            isNewBrand={isNewBrand}
          />
        )}
      </div>
    </div>
  )
}
