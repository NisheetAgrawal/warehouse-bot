import { useCallback, useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import { api } from "../lib/api"
import BottomNav from "../components/BottomNav"

const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000"

function timeAgo(dateStr) {
  if (!dateStr) return ""
  const diff = Date.now() - new Date(dateStr + "T00:00:00").getTime()
  const days = Math.floor(diff / 86400000)
  if (days === 0) return "Aaj"
  if (days === 1) return "Kal"
  return `${days} din pehle`
}

function formatDate(dateStr) {
  if (!dateStr) return ""
  const d = new Date(dateStr + "T00:00:00")
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })
}

// ── Challan card ─────────────────────────────────────────────────
function ChallanCard({ challan }) {
  const [expanded, setExpanded] = useState(false)
  const [pdfLoading, setPdfLoading] = useState(false)

  const totalQty = challan.items.reduce((s, i) => s + (i.quantity || 0), 0)

  async function regeneratePdf() {
    setPdfLoading(true)
    try {
      const res = await fetch(`${BASE}/api/challan/pdf`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          vehicle_no: challan.vehicle_no,
          operator:   challan.operator || "Swayam",
          party:      challan.party    || "",
          items:      challan.items.map((i) => ({
            brand:    i.brand,
            spec:     i.spec,
            type:     "",
            quantity: i.quantity,
            unit:     "nos",
          })),
        }),
      })
      if (res.ok) {
        const blob = await res.blob()
        const url  = URL.createObjectURL(blob)
        window.open(url, "_blank")
      }
    } catch (e) {
      console.error(e)
    } finally {
      setPdfLoading(false)
    }
  }

  return (
    <div
      className="rounded-2xl overflow-hidden"
      style={{
        background: "rgba(255,255,255,0.04)",
        border: "1px solid rgba(255,255,255,0.07)",
      }}
    >
      {/* Card header — tap to expand */}
      <button
        onClick={() => setExpanded((e) => !e)}
        className="w-full flex items-center gap-3 px-4 py-4 text-left"
        style={{ background: "none", border: "none", cursor: "pointer" }}
      >
        {/* Vehicle + party */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <p style={{
            margin: 0, fontSize: 17, fontWeight: 700, color: "#E8500A",
            fontFamily: "'DM Mono', monospace", letterSpacing: "0.04em",
            overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
          }}>
            {challan.vehicle_no}
          </p>
          {challan.party && (
            <p style={{ margin: "2px 0 0", fontSize: 12, color: "rgba(255,255,255,0.5)",
                        fontFamily: "'DM Sans', sans-serif" }}>
              → {challan.party}
            </p>
          )}
        </div>

        {/* Date + item count */}
        <div style={{ textAlign: "right", flexShrink: 0 }}>
          <p style={{ margin: 0, fontSize: 12, color: "rgba(255,255,255,0.5)",
                      fontFamily: "'DM Sans', sans-serif" }}>
            {timeAgo(challan.date)}
          </p>
          <p style={{ margin: "2px 0 0", fontSize: 11, color: "rgba(255,255,255,0.3)",
                      fontFamily: "'DM Mono', monospace" }}>
            {challan.items.length} items · {totalQty} units
          </p>
        </div>

        {/* Expand chevron */}
        <svg
          width="16" height="16" viewBox="0 0 24 24" fill="none"
          stroke="rgba(255,255,255,0.3)" strokeWidth="2"
          strokeLinecap="round" strokeLinejoin="round"
          style={{
            transform: expanded ? "rotate(180deg)" : "rotate(0deg)",
            transition: "transform 0.2s ease",
            flexShrink: 0,
          }}
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>

      {/* Expanded items + PDF button */}
      {expanded && (
        <div style={{ borderTop: "1px solid rgba(255,255,255,0.06)" }}>
          {/* Items list */}
          <div className="px-4 py-3 flex flex-col gap-2">
            <p style={{
              fontSize: 10, color: "rgba(255,255,255,0.3)", margin: "0 0 6px",
              textTransform: "uppercase", letterSpacing: "0.1em",
              fontFamily: "'DM Sans', sans-serif",
            }}>
              {formatDate(challan.date)}
            </p>
            {challan.items.map((item, i) => (
              <div key={i} className="flex items-center justify-between gap-2">
                <p style={{
                  margin: 0, fontSize: 13, color: "#fff", flex: 1, minWidth: 0,
                  fontFamily: "'DM Sans', sans-serif",
                  overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                }}>
                  {item.brand} {item.spec}
                </p>
                <span style={{
                  fontSize: 13, fontWeight: 700, color: "#fff",
                  fontFamily: "'DM Mono', monospace", flexShrink: 0,
                }}>
                  ×{item.quantity}
                </span>
              </div>
            ))}
          </div>

          {/* PDF regenerate button */}
          <div style={{ padding: "8px 16px 14px" }}>
            <button
              onClick={regeneratePdf}
              disabled={pdfLoading}
              style={{
                width: "100%", padding: "12px",
                borderRadius: 14, border: "1px solid rgba(232,80,10,0.3)",
                background: "rgba(232,80,10,0.1)",
                color: pdfLoading ? "rgba(255,255,255,0.3)" : "#E8500A",
                cursor: pdfLoading ? "not-allowed" : "pointer",
                fontFamily: "'DM Sans', sans-serif",
                fontSize: 13, fontWeight: 600,
              }}
            >
              {pdfLoading ? "PDF ban raha hai..." : "📄 PDF Banao"}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}


// ── Challans page ─────────────────────────────────────────────────
export default function Challans() {
  const navigate = useNavigate()
  const [challans, setChallans] = useState([])
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState(null)
  const [refreshing, setRefreshing] = useState(false)

  useEffect(() => {
    if (!localStorage.getItem("auth")) navigate("/login", { replace: true })
  }, [navigate])

  const load = useCallback(async (showSpinner = true) => {
    if (showSpinner) setLoading(true)
    else setRefreshing(true)
    setError(null)
    try {
      const data = await api.challans()
      setChallans(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

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
              width: 36, height: 36, borderRadius: 12, border: "none",
              background: "rgba(255,255,255,0.07)", cursor: "pointer",
              display: "flex", alignItems: "center", justifyContent: "center",
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
              Challans
            </h1>
            <p style={{ fontSize: 12, color: "rgba(255,255,255,0.35)", margin: 0 }}>
              Last 7 days — {challans.length} deliveries
            </p>
          </div>
        </div>

        {/* Refresh */}
        <button
          onClick={() => load(false)}
          disabled={refreshing}
          style={{
            width: 36, height: 36, borderRadius: 12, border: "none",
            background: "rgba(255,255,255,0.07)", cursor: "pointer",
            display: "flex", alignItems: "center", justifyContent: "center",
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

      <div className="px-5 flex flex-col gap-3">
        {loading && (
          <>
            {[1, 2, 3].map((i) => (
              <div key={i} className="rounded-2xl"
                   style={{ height: 80, background: "rgba(255,255,255,0.04)",
                            border: "1px solid rgba(255,255,255,0.07)", opacity: 1 - i * 0.25 }} />
            ))}
          </>
        )}

        {!loading && error && (
          <div className="rounded-2xl px-4 py-4 text-center"
               style={{ background: "rgba(248,113,113,0.08)", border: "1px solid rgba(248,113,113,0.25)" }}>
            <p style={{ margin: 0, fontSize: 13, color: "#F87171" }}>❌ {error}</p>
            <button onClick={() => load()} style={{ marginTop: 8, fontSize: 12, color: "#E8500A",
                                                     background: "none", border: "none", cursor: "pointer" }}>
              Dobara try karo →
            </button>
          </div>
        )}

        {!loading && !error && challans.length === 0 && (
          <div className="flex flex-col items-center justify-center py-16 gap-3"
               style={{ color: "rgba(255,255,255,0.2)" }}>
            <span style={{ fontSize: 40 }}>📋</span>
            <p style={{ margin: 0, fontSize: 13 }}>Last 7 din mein koi challan nahi</p>
          </div>
        )}

        {!loading && !error && challans.map((challan) => (
          <ChallanCard key={challan.key} challan={challan} />
        ))}
      </div>

      <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
      <BottomNav active="challans" />
    </div>
  )
}
