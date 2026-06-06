import { useEffect, useRef, useState } from "react"

const CAT_EMOJI = {
  "Solar Panel":  "☀️",
  "Inverter":     "⚡",
  "ACDB/DCDB":   "🔌",
  "Cable":        "🔗",
  "PVC Material": "🧱",
  "Structure":    "🏗️",
  "General":      "📦",
}

/**
 * Reusable product search input + dropdown.
 * Props:
 *   search(query) → [product]  (from useProducts hook)
 *   onSelect(product)          — called when user picks a suggestion
 *   loading                    — shows placeholder text while products load
 *   placeholder                — custom placeholder string
 *   isSelected(product_id)     — optional fn to mark already-added items
 */
export default function ProductSearch({
  search,
  onSelect,
  loading,
  placeholder = "Product ka naam type karo...",
  isSelected,
}) {
  const [query, setQuery]           = useState("")
  const [suggestions, setSuggestions] = useState([])
  const [showDrop, setShowDrop]     = useState(false)
  const dropRef  = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => {
    const results = search(query)
    setSuggestions(results)
    setShowDrop(results.length > 0 && query.trim().length >= 2)
  }, [query])

  useEffect(() => {
    function handler(e) {
      if (
        dropRef.current  && !dropRef.current.contains(e.target) &&
        inputRef.current && !inputRef.current.contains(e.target)
      ) {
        setShowDrop(false)
      }
    }
    document.addEventListener("mousedown", handler)
    return () => document.removeEventListener("mousedown", handler)
  }, [])

  function handleSelect(product) {
    setQuery("")
    setShowDrop(false)
    onSelect(product)
  }

  return (
    <div className="relative">
      {/* Input */}
      <div className="relative">
        <input
          ref={inputRef}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => suggestions.length > 0 && setShowDrop(true)}
          placeholder={loading ? "Products load ho rahe hain..." : placeholder}
          disabled={loading}
          className="w-full rounded-2xl px-4 py-4 text-white outline-none"
          style={{
            background:  "rgba(255,255,255,0.05)",
            border:      "1.5px solid rgba(255,255,255,0.08)",
            fontFamily:  "'DM Sans', sans-serif",
            fontSize:    15,
            boxSizing:   "border-box",
          }}
          autoComplete="off"
          spellCheck={false}
        />
        {query && (
          <button
            onClick={() => { setQuery(""); setShowDrop(false) }}
            style={{
              position: "absolute", right: 14, top: "50%",
              transform: "translateY(-50%)",
              background: "none", border: "none",
              color: "rgba(255,255,255,0.3)", cursor: "pointer",
              fontSize: 16, padding: 0,
            }}
          >
            ✕
          </button>
        )}
      </div>

      {/* Dropdown */}
      {showDrop && (
        <div
          ref={dropRef}
          style={{
            position: "absolute", left: 0, right: 0,
            top: "calc(100% + 8px)", zIndex: 50,
            background: "#16161E",
            border: "1px solid rgba(255,255,255,0.1)",
            borderRadius: 20,
            boxShadow: "0 20px 40px rgba(0,0,0,0.6)",
            overflow: "hidden",
            maxHeight: 300,
            overflowY: "auto",
          }}
        >
          {suggestions.map((p, i) => {
            const selected = isSelected?.(p.product_id)
            return (
              <button
                key={p.product_id}
                onClick={() => handleSelect(p)}
                style={{
                  width: "100%", display: "flex", alignItems: "center",
                  gap: 12, padding: "12px 16px", textAlign: "left",
                  background: selected ? "rgba(232,80,10,0.08)" : "transparent",
                  border: "none",
                  borderBottom: i < suggestions.length - 1
                    ? "1px solid rgba(255,255,255,0.05)"
                    : "none",
                  cursor: "pointer",
                }}
              >
                <span style={{ fontSize: 20, flexShrink: 0 }}>
                  {CAT_EMOJI[p.category] || "📦"}
                </span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <p style={{
                    margin: 0, fontSize: 13, fontWeight: 600, color: "#fff",
                    fontFamily: "'DM Sans', sans-serif",
                    overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                  }}>
                    {p.brand}
                    {p.spec  ? ` · ${p.spec}`  : ""}
                    {p.type_ ? ` ${p.type_}` : ""}
                  </p>
                  <p style={{
                    margin: 0, fontSize: 11,
                    color: (p.quantity || 0) === 0
                      ? "#F87171"
                      : (p.quantity || 0) < 5
                      ? "#FACC15"
                      : "rgba(255,255,255,0.35)",
                    fontFamily: "'DM Mono', monospace",
                  }}>
                    {p.quantity ?? 0} {p.unit || "nos"} in stock
                  </p>
                </div>
                {selected && (
                  <span style={{
                    fontSize: 10, color: "#E8500A", flexShrink: 0,
                    fontFamily: "'DM Sans', sans-serif",
                  }}>
                    Added
                  </span>
                )}
              </button>
            )
          })}
        </div>
      )}

      {/* No results */}
      {query.trim().length >= 2 && suggestions.length === 0 && !loading && (
        <div
          ref={dropRef}
          style={{
            position: "absolute", left: 0, right: 0,
            top: "calc(100% + 8px)", zIndex: 50,
            background: "#16161E",
            border: "1px solid rgba(255,255,255,0.1)",
            borderRadius: 20,
            padding: "20px 16px",
            textAlign: "center",
            fontSize: 13,
            color: "rgba(255,255,255,0.35)",
            fontFamily: "'DM Sans', sans-serif",
          }}
        >
          Koi match nahi mila
        </div>
      )}
    </div>
  )
}
