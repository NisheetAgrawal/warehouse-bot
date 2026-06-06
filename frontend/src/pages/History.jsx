import { useCallback, useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import { api } from "../lib/api"
import BottomNav from "../components/BottomNav"

// ── Helpers ────────────────────────────────────────────────────────
function timeAgo(isoString) {
  if (!isoString) return ""
  const date = new Date(isoString)
  const diffMs = Date.now() - date.getTime()
  const diffMin  = Math.floor(diffMs / 60000)
  const diffHour = Math.floor(diffMs / 3600000)
  const diffDay  = Math.floor(diffMs / 86400000)

  if (diffMin < 1)   return "abhi"
  if (diffMin < 60)  return `${diffMin}m pehle`
  if (diffHour < 24) return `${diffHour}h pehle`
  if (diffDay === 1) return "kal"
  if (diffDay < 7)   return `${diffDay} din pehle`
  return date.toLocaleDateString("en-IN", { day: "numeric", month: "short" })
}

function isToday(isoString) {
  if (!isoString) return false
  const d = new Date(isoString)
  const now = new Date()
  return d.getDate() === now.getDate() &&
         d.getMonth() === now.getMonth() &&
         d.getFullYear() === now.getFullYear()
}

function isThisWeek(isoString) {
  if (!isoString) return false
  const diffMs = Date.now() - new Date(isoString).getTime()
  return diffMs < 7 * 24 * 3600 * 1000
}

const FILTERS = [
  { key: "all",   label: "All" },
  { key: "today", label: "Aaj" },
  { key: "week",  label: "Is Hafte" },
]

// ── Transaction row ───────────────────────────────────────────────
function TxRow({ tx }) {
  const isIn   = tx.type_ === "ADD_IN"
  const absQty = Math.abs(tx.qty_change ?? 0)

  return (
    <div
      className="flex items-center gap-3 px-4 py-3 rounded-2xl"
      style={{
        background: "rgba(255,255,255,0.04)",
        border: "1px solid rgba(255,255,255,0.06)",
      }}
    >
      {/* IN / OUT badge */}
      <span
        className="flex-shrink-0 rounded-xl px-2 py-1 text-center"
        style={{
          fontSize: 10, fontWeight: 700, letterSpacing: "0.05em",
          minWidth: 36,
          backgroundColor: isIn
            ? "rgba(52,211,153,0.15)"
            : "rgba(248,113,113,0.15)",
          color:           isIn ? "#34D399" : "#F87171",
          border: `1px solid ${isIn ? "rgba(52,211,153,0.3)" : "rgba(248,113,113,0.3)"}`,
          fontFamily: "'DM Sans', sans-serif",
        }}
      >
        {isIn ? "IN" : "OUT"}
      </span>

      {/* Details */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <p style={{
          margin: 0, fontSize: 13, fontWeight: 600, color: "#fff",
          fontFamily: "'DM Sans', sans-serif",
          overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
        }}>
          {tx.brand} {tx.spec}
        </p>
        <p style={{
          margin: 0, fontSize: 11, color: "rgba(255,255,255,0.35)",
          fontFamily: "'DM Sans', sans-serif",
          overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
        }}>
          {tx.party || (tx.vehicle_no ? `🚛 ${tx.vehicle_no}` : "")}
          {!tx.party && !tx.vehicle_no ? tx.operator || "" : ""}
        </p>
      </div>

      {/* Qty + time */}
      <div style={{ flexShrink: 0, textAlign: "right" }}>
        <p style={{
          margin: 0, fontSize: 15, fontWeight: 700,
          color: isIn ? "#34D399" : "#F87171",
          fontFamily: "'DM Mono', monospace",
        }}>
          {isIn ? "+" : "−"}{absQty}
        </p>
        <p style={{
          margin: 0, fontSize: 10, color: "rgba(255,255,255,0.3)",
          fontFamily: "'DM Sans', sans-serif",
        }}>
          {timeAgo(tx.timestamp)}
        </p>
      </div>
    </div>
  )
}

// ── History page ──────────────────────────────────────────────────
export default function History() {
  const navigate = useNavigate()
  const [txns, setTxns]       = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)
  const [filter, setFilter]   = useState("all")
  const [refreshing, setRefreshing] = useState(false)

  useEffect(() => {
    if (!localStorage.getItem("auth")) navigate("/login", { replace: true })
  }, [navigate])

  const load = useCallback(async (showSpinner = true) => {
    if (showSpinner) setLoading(true)
    else setRefreshing(true)
    setError(null)
    try {
      const data = await api.transactions()
      setTxns(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  // Apply filter
  const filtered = txns.filter((tx) => {
    if (filter === "today") return isToday(tx.timestamp)
    if (filter === "week")  return isThisWeek(tx.timestamp)
    return true
  })

  return (
    <div
      className="min-h-dvh flex flex-col pb-28"
      style={{ backgroundColor: "#0A0A0F", fontFamily: "'DM Sans', sans-serif" }}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-5 pt-14 pb-4">
        <div className="flex items-center gap-3">
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
              History
            </h1>
            <p style={{ fontSize: 12, color: "rgba(255,255,255,0.35)", margin: 0 }}>
              {txns.length} transactions
            </p>
          </div>
        </div>

        {/* Refresh button */}
        <button
          onClick={() => load(false)}
          disabled={refreshing}
          style={{
            display: "flex", alignItems: "center", justifyContent: "center",
            width: 36, height: 36, borderRadius: 12,
            background: "rgba(255,255,255,0.07)", border: "none", cursor: "pointer",
          }}
        >
          <svg
            width="16" height="16" viewBox="0 0 24 24" fill="none"
            stroke={refreshing ? "#E8500A" : "rgba(255,255,255,0.6)"}
            strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"
            style={{ animation: refreshing ? "spin 1s linear infinite" : "none" }}
          >
            <polyline points="23 4 23 10 17 10" />
            <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
          </svg>
        </button>
      </div>

      {/* Filter tabs */}
      <div className="flex gap-2 px-5 mb-4">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            style={{
              padding: "7px 16px",
              borderRadius: 20,
              border: "none",
              cursor: "pointer",
              fontFamily: "'DM Sans', sans-serif",
              fontSize: 13,
              fontWeight: filter === f.key ? 600 : 400,
              backgroundColor: filter === f.key
                ? "#E8500A"
                : "rgba(255,255,255,0.07)",
              color: filter === f.key ? "#fff" : "rgba(255,255,255,0.45)",
              transition: "all 0.2s ease",
            }}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="px-5 flex flex-col gap-2">
        {loading && (
          <>
            {[1, 2, 3, 4, 5].map((i) => (
              <div
                key={i}
                className="rounded-2xl"
                style={{
                  height: 60,
                  background: "rgba(255,255,255,0.04)",
                  border: "1px solid rgba(255,255,255,0.06)",
                  opacity: 1 - i * 0.15,
                }}
              />
            ))}
          </>
        )}

        {!loading && error && (
          <div
            className="rounded-2xl px-4 py-4 text-center"
            style={{
              background: "rgba(248,113,113,0.08)",
              border: "1px solid rgba(248,113,113,0.25)",
            }}
          >
            <p style={{ margin: 0, fontSize: 13, color: "#F87171" }}>
              ❌ Data nahi aaya: {error}
            </p>
            <button
              onClick={() => load()}
              style={{
                marginTop: 8, fontSize: 12, color: "#E8500A",
                background: "none", border: "none", cursor: "pointer",
              }}
            >
              Dobara try karo →
            </button>
          </div>
        )}

        {!loading && !error && filtered.length === 0 && (
          <div
            className="flex flex-col items-center justify-center py-16 gap-3"
            style={{ color: "rgba(255,255,255,0.2)" }}
          >
            <span style={{ fontSize: 40 }}>📋</span>
            <p style={{ margin: 0, fontSize: 13 }}>
              {filter === "today"
                ? "Aaj koi transaction nahi"
                : filter === "week"
                ? "Is hafte koi transaction nahi"
                : "Koi transaction nahi mili"}
            </p>
          </div>
        )}

        {!loading && !error && filtered.map((tx) => (
          <TxRow key={tx.id} tx={tx} />
        ))}
      </div>

      <style>{`@keyframes spin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}`}</style>
      <BottomNav active="party" />
    </div>
  )
}
