import { useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import { api } from "../lib/api"
import BottomNav from "../components/BottomNav"

// ── Category emoji ───────────────────────────────────────────────
const CAT_EMOJI = {
  "Solar Panel":  "☀️",
  "Inverter":     "⚡",
  "ACDB/DCDB":   "🔌",
  "Cable":        "🔗",
  "PVC Material": "🧱",
  "Structure":    "🏗️",
  "General":      "📦",
}

// ── Quick actions ────────────────────────────────────────────────
const ACTIONS = [
  {
    id: "stock-in",
    label: "Maal Aaya",
    desc:  "Stock receive karo",
    color: "#E8500A",
    path:  "/stock-in",
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M5 12h14M12 5l7 7-7 7" />
      </svg>
    ),
  },
  {
    id: "challan",
    label: "Truck Loading",
    desc:  "Challan banao",
    color: "#1A6BF0",
    path:  "/challan",
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="1" y="3" width="15" height="13" rx="1" />
        <path d="M16 8h4l3 3v5h-7V8z" />
        <circle cx="5.5" cy="18.5" r="2.5" />
        <circle cx="18.5" cy="18.5" r="2.5" />
      </svg>
    ),
  },
  {
    id: "stock-check",
    label: "Stock Check",
    desc:  "Inventory dekho",
    color: "#059669",
    path:  "/stock-check",
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="11" cy="11" r="8" />
        <line x1="21" y1="21" x2="16.65" y2="16.65" />
      </svg>
    ),
  },
  {
    id: "history",
    label: "History",
    desc:  "Transactions dekho",
    color: "#7C3AED",
    path:  "/history",
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
        <polyline points="12 8 12 12 14 14" />
        <path d="M3.05 11a9 9 0 1 1 .5 4M3 16v-5h5" />
      </svg>
    ),
  },
]

// ── Stat card ────────────────────────────────────────────────────
function StatCard({ dot, label, value, loading }) {
  return (
    <div
      className="flex-1 flex flex-col gap-1.5 px-3 py-3 rounded-2xl"
      style={{
        background: "rgba(255,255,255,0.04)",
        border: "1px solid rgba(255,255,255,0.07)",
        minWidth: 0,
      }}
    >
      <div className="flex items-center gap-1.5">
        <span
          className="rounded-full flex-shrink-0"
          style={{ width: 7, height: 7, backgroundColor: dot }}
        />
        <span
          style={{
            fontSize: 10,
            color: "rgba(255,255,255,0.4)",
            fontFamily: "'DM Sans', sans-serif",
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis",
          }}
        >
          {label}
        </span>
      </div>
      <span
        style={{
          fontSize: 22,
          fontWeight: 700,
          color: loading ? "rgba(255,255,255,0.15)" : "#fff",
          fontFamily: "'DM Sans', sans-serif",
          letterSpacing: "-0.5px",
          lineHeight: 1,
        }}
      >
        {loading ? "—" : value}
      </span>
    </div>
  )
}

// ── Action card ──────────────────────────────────────────────────
function ActionCard({ action, onClick }) {
  return (
    <button
      onClick={onClick}
      className="flex flex-col gap-3 p-4 rounded-2xl text-left transition-transform active:scale-95"
      style={{
        backgroundColor: action.color,
        border: "none",
        cursor: "pointer",
        backgroundImage: `radial-gradient(circle at top right, rgba(255,255,255,0.12), transparent 65%)`,
      }}
    >
      {/* Icon box */}
      <span
        className="flex items-center justify-center rounded-xl"
        style={{
          width: 40,
          height: 40,
          background: "rgba(0,0,0,0.2)",
          color: "#fff",
        }}
      >
        {action.icon}
      </span>

      {/* Text */}
      <div className="flex flex-col gap-0.5">
        <span
          style={{
            fontSize: 13,
            fontWeight: 600,
            color: "#fff",
            fontFamily: "'DM Sans', sans-serif",
          }}
        >
          {action.label}
        </span>
        <span
          style={{
            fontSize: 10,
            color: "rgba(255,255,255,0.6)",
            fontFamily: "'DM Sans', sans-serif",
          }}
        >
          {action.desc}
        </span>
      </div>
    </button>
  )
}

// ── Low stock row ────────────────────────────────────────────────
function LowStockRow({ product }) {
  const emoji = CAT_EMOJI[product.category] || "📦"
  const isOut = product.quantity === 0

  return (
    <div
      className="flex items-center gap-3 px-4 py-3 rounded-2xl"
      style={{
        background: "rgba(255,255,255,0.04)",
        border: "1px solid rgba(255,255,255,0.07)",
      }}
    >
      {/* Emoji */}
      <span style={{ fontSize: 20, flexShrink: 0 }}>{emoji}</span>

      {/* Name + spec */}
      <div className="flex-1 min-w-0">
        <p
          className="truncate"
          style={{
            fontSize: 13,
            fontWeight: 600,
            color: "#fff",
            fontFamily: "'DM Sans', sans-serif",
            margin: 0,
          }}
        >
          {product.brand}
        </p>
        {product.spec && (
          <p
            className="truncate"
            style={{
              fontSize: 11,
              color: "rgba(255,255,255,0.35)",
              fontFamily: "'DM Sans', sans-serif",
              margin: 0,
            }}
          >
            {product.spec} {product.type_}
          </p>
        )}
      </div>

      {/* Badge */}
      <span
        className="flex-shrink-0 px-2 py-0.5 rounded-lg"
        style={{
          fontSize: 11,
          fontWeight: 600,
          fontFamily: "'DM Mono', monospace",
          backgroundColor: isOut
            ? "rgba(248,113,113,0.15)"
            : "rgba(250,204,21,0.15)",
          color: isOut ? "#F87171" : "#FACC15",
          border: `1px solid ${isOut ? "rgba(248,113,113,0.25)" : "rgba(250,204,21,0.25)"}`,
        }}
      >
        {isOut ? "Out" : `${product.quantity} left`}
      </span>
    </div>
  )
}


// ── Home page ────────────────────────────────────────────────────
export default function Home() {
  const navigate = useNavigate()
  const [products, setProducts] = useState([])
  const [loading, setLoading] = useState(true)
  const [time, setTime] = useState("")
  const [error, setError] = useState(null)

  // Auth guard
  useEffect(() => {
    if (!localStorage.getItem("auth")) navigate("/login", { replace: true })
  }, [navigate])

  // Live clock
  useEffect(() => {
    const tick = () => {
      const now = new Date()
      setTime(now.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", hour12: true }))
    }
    tick()
    const id = setInterval(tick, 30000)
    return () => clearInterval(id)
  }, [])

  // Fetch products
  useEffect(() => {
    api.products()
      .then((data) => { setProducts(data); setLoading(false) })
      .catch((err) => { setError(err.message); setLoading(false) })
  }, [])

  // Computed stats
  const inStockCount  = products.filter((p) => (p.quantity || 0) >= 5).length
  const lowStockList  = products.filter((p) => (p.quantity || 0) > 0 && (p.quantity || 0) < 5)
  const outStockCount = products.filter((p) => (p.quantity || 0) === 0).length
  const alertList     = [...lowStockList, ...products.filter((p) => (p.quantity || 0) === 0)].slice(0, 10)

  return (
    <div
      className="min-h-dvh flex flex-col"
      style={{ backgroundColor: "#0A0A0F", fontFamily: "'DM Sans', sans-serif", paddingBottom: 80 }}
    >
      {/* ── Top section ── */}
      <div className="px-5 pt-14 pb-2">
        {/* Status bar row */}
        <div className="flex items-center justify-between mb-5">
          <span
            style={{
              fontSize: 13,
              fontWeight: 500,
              color: "rgba(255,255,255,0.5)",
              fontFamily: "'DM Mono', monospace",
            }}
          >
            {time}
          </span>
          <span
            style={{
              fontSize: 10,
              letterSpacing: "0.12em",
              textTransform: "uppercase",
              color: "rgba(255,255,255,0.3)",
              fontFamily: "'DM Sans', sans-serif",
              fontWeight: 500,
            }}
          >
            Swadev Energies
          </span>
        </div>

        {/* Greeting */}
        <h1
          style={{
            fontSize: 26,
            fontWeight: 600,
            color: "#fff",
            margin: 0,
            letterSpacing: "-0.4px",
            lineHeight: 1.2,
          }}
        >
          Namaste, Swayam ☀️
        </h1>
        <p
          style={{
            fontSize: 12,
            color: "rgba(255,255,255,0.35)",
            margin: "4px 0 0",
            fontFamily: "'DM Sans', sans-serif",
          }}
        >
          Aaj ka update karo
        </p>
      </div>

      {/* ── Stats strip ── */}
      <div className="px-5 mt-5 flex gap-2.5">
        <StatCard
          dot="#34D399"
          label="In Stock"
          value={inStockCount}
          loading={loading}
        />
        <StatCard
          dot="#FACC15"
          label="Low Stock"
          value={lowStockList.length}
          loading={loading}
        />
        <StatCard
          dot="#F87171"
          label="Out of Stock"
          value={outStockCount}
          loading={loading}
        />
      </div>

      {/* ── Quick actions 2×2 grid ── */}
      <div className="px-5 mt-6">
        <p
          style={{
            fontSize: 10,
            letterSpacing: "0.1em",
            textTransform: "uppercase",
            color: "rgba(255,255,255,0.3)",
            fontWeight: 500,
            margin: "0 0 12px",
          }}
        >
          Quick Actions
        </p>
        <div className="grid grid-cols-2 gap-3">
          {ACTIONS.map((action) => (
            <ActionCard
              key={action.id}
              action={action}
              onClick={() => navigate(action.path)}
            />
          ))}
        </div>

        {/* Naya Product — full-width 5th action */}
        <button
          onClick={() => navigate("/add-product")}
          className="w-full mt-3 flex items-center gap-4 px-5 py-4 rounded-2xl transition-transform active:scale-95"
          style={{
            backgroundColor: "rgba(14,165,233,0.12)",
            border: "1px solid rgba(14,165,233,0.25)",
            cursor: "pointer",
            backgroundImage: "radial-gradient(circle at right, rgba(14,165,233,0.08), transparent 60%)",
          }}
        >
          <span
            className="flex items-center justify-center rounded-xl"
            style={{ width: 40, height: 40, background: "rgba(14,165,233,0.2)", flexShrink: 0 }}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
                 stroke="#0EA5E9" strokeWidth="2.2"
                 strokeLinecap="round" strokeLinejoin="round">
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
          </span>
          <div className="text-left">
            <p style={{ margin: 0, fontSize: 13, fontWeight: 600, color: "#fff",
                        fontFamily: "'DM Sans', sans-serif" }}>
              Naya Product
            </p>
            <p style={{ margin: 0, fontSize: 10, color: "rgba(255,255,255,0.4)",
                        fontFamily: "'DM Sans', sans-serif" }}>
              AI se product add karo
            </p>
          </div>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
               stroke="rgba(255,255,255,0.25)" strokeWidth="2"
               strokeLinecap="round" strokeLinejoin="round"
               style={{ marginLeft: "auto" }}>
            <polyline points="9 18 15 12 9 6" />
          </svg>
        </button>
      </div>

      {/* ── Low / out stock section ── */}
      <div className="px-5 mt-6">
        <p
          style={{
            fontSize: 10,
            letterSpacing: "0.1em",
            textTransform: "uppercase",
            color: "rgba(255,255,255,0.3)",
            fontWeight: 500,
            margin: "0 0 12px",
          }}
        >
          Kam Stock
        </p>

        {loading && (
          <div className="flex flex-col gap-2">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="rounded-2xl"
                style={{
                  height: 56,
                  background: "rgba(255,255,255,0.04)",
                  border: "1px solid rgba(255,255,255,0.07)",
                }}
              />
            ))}
          </div>
        )}

        {!loading && error && (
          <p style={{ color: "#F87171", fontSize: 13 }}>
            API se data nahi aaya: {error}
          </p>
        )}

        {!loading && !error && alertList.length === 0 && (
          <p style={{ color: "rgba(255,255,255,0.3)", fontSize: 13 }}>
            Sab stock theek hai 🎉
          </p>
        )}

        {!loading && !error && (
          <div className="flex flex-col gap-2">
            {alertList.map((p) => (
              <LowStockRow key={p.id} product={p} />
            ))}
          </div>
        )}
      </div>

      {/* ── Bottom nav ── */}
      <BottomNav active="home" />
    </div>
  )
}
