import { useNavigate } from "react-router-dom"

const TABS = [
  {
    id: "home",
    label: "Home",
    path: "/home",
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M3 9.5L12 3l9 6.5V20a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9.5z" />
        <path d="M9 21V12h6v9" />
      </svg>
    ),
  },
  {
    id: "stock",
    label: "Stock",
    path: "/stock-check",
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="2" y="3" width="20" height="14" rx="2" />
        <path d="M8 21h8M12 17v4" />
      </svg>
    ),
  },
  {
    id: "challans",
    label: "Challans",
    path: "/challan",
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14 2 14 8 20 8" />
        <line x1="16" y1="13" x2="8" y2="13" />
        <line x1="16" y1="17" x2="8" y2="17" />
        <polyline points="10 9 9 9 8 9" />
      </svg>
    ),
  },
  {
    id: "party",
    label: "Party",
    path: "/history",
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
        <circle cx="9" cy="7" r="4" />
        <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
        <path d="M16 3.13a4 4 0 0 1 0 7.75" />
      </svg>
    ),
  },
]

export default function BottomNav({ active }) {
  const navigate = useNavigate()

  return (
    <nav
      className="fixed bottom-0 left-0 right-0 flex items-center justify-around px-2 py-3"
      style={{
        backgroundColor: "#0F0F16",
        borderTop: "1px solid rgba(255,255,255,0.06)",
        paddingBottom: "calc(12px + env(safe-area-inset-bottom))",
      }}
    >
      {TABS.map((tab) => {
        const isActive = tab.id === active
        return (
          <button
            key={tab.id}
            onClick={() => navigate(tab.path)}
            className="flex flex-col items-center gap-1 relative px-4 py-1 transition-opacity active:opacity-60"
            style={{ background: "none", border: "none", cursor: "pointer" }}
          >
            {/* Icon */}
            <span style={{ color: isActive ? "#E8500A" : "rgba(255,255,255,0.25)" }}>
              {tab.icon}
            </span>

            {/* Label */}
            <span
              style={{
                fontSize: "10px",
                fontFamily: "'DM Sans', sans-serif",
                fontWeight: isActive ? 600 : 400,
                color: isActive ? "#E8500A" : "rgba(255,255,255,0.25)",
              }}
            >
              {tab.label}
            </span>

            {/* Active dot */}
            {isActive && (
              <span
                className="absolute bottom-0"
                style={{
                  width: 4,
                  height: 4,
                  borderRadius: "50%",
                  backgroundColor: "#E8500A",
                  bottom: -2,
                }}
              />
            )}
          </button>
        )
      })}
    </nav>
  )
}
