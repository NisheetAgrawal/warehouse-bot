import { useEffect, useRef, useState } from "react"

/**
 * Reusable +/qty/- control where the number in the middle is tappable.
 * Tap qty number → inline input with orange bottom border, DM Mono.
 * Blur or Enter commits. Minimum value 1 (never removes item unlike − button).
 * Used in Challan.jsx and StockIn.jsx.
 *
 * Props:
 *   qty         — current quantity
 *   productId   — identifier for this item
 *   onDelta(id, delta) — called by +/− buttons (delta = +1 or -1)
 *   onDirectSet(id, n) — called when user types a number directly
 */
export default function QtyControl({ qty, productId, onDelta, onDirectSet }) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft]     = useState(String(qty))
  const inputRef              = useRef(null)

  // Keep draft in sync when qty changes from outside (+/− buttons)
  useEffect(() => {
    if (!editing) setDraft(String(qty))
  }, [qty, editing])

  useEffect(() => {
    if (editing && inputRef.current) {
      inputRef.current.focus()
      inputRef.current.select()
    }
  }, [editing])

  function commit() {
    const n = parseInt(draft, 10)
    if (!isNaN(n) && n >= 1) {
      onDirectSet(productId, n)
    } else {
      setDraft(String(qty))   // revert invalid input
    }
    setEditing(false)
  }

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
      {/* Minus — design unchanged */}
      <button
        onClick={() => onDelta(productId, -1)}
        style={{
          width: 32, height: 32, borderRadius: 10,
          background: "rgba(255,255,255,0.1)", border: "none",
          cursor: "pointer", color: "rgba(255,255,255,0.7)", fontSize: 18,
          display: "flex", alignItems: "center", justifyContent: "center",
        }}
      >
        −
      </button>

      {/* Qty number (tappable) → inline input on tap */}
      {editing ? (
        <input
          ref={inputRef}
          type="number"
          min="1"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={commit}
          onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); commit() } }}
          style={{
            width: 48,
            textAlign: "center",
            fontFamily: "'DM Mono', monospace",
            fontSize: 15,
            fontWeight: 600,
            color: "#fff",
            background: "transparent",
            border: "none",
            borderBottom: "2px solid #E8500A",
            outline: "none",
            padding: "2px 0",
            MozAppearance: "textfield",
          }}
        />
      ) : (
        <span
          onClick={() => { setDraft(String(qty)); setEditing(true) }}
          title="Tap to type quantity"
          style={{
            minWidth: 28,
            textAlign: "center",
            fontSize: 15,
            fontWeight: 600,
            color: "#fff",
            fontFamily: "'DM Mono', monospace",
            cursor: "pointer",
            padding: "2px 4px",
            borderRadius: 4,
          }}
        >
          {qty}
        </span>
      )}

      {/* Plus — design unchanged */}
      <button
        onClick={() => onDelta(productId, 1)}
        style={{
          width: 32, height: 32, borderRadius: 10,
          background: "#E8500A", border: "none",
          cursor: "pointer", color: "#fff", fontSize: 18,
          display: "flex", alignItems: "center", justifyContent: "center",
        }}
      >
        +
      </button>
    </div>
  )
}
