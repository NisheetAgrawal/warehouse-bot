import { useState } from "react"
import { useNavigate } from "react-router-dom"

const PASSWORD = "solar@2024"

function SunIcon() {
  return (
    <svg
      width="36"
      height="36"
      viewBox="0 0 36 36"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      {/* Center circle */}
      <circle cx="18" cy="18" r="7" fill="white" />
      {/* Rays */}
      {[0, 45, 90, 135, 180, 225, 270, 315].map((deg) => {
        const rad = (deg * Math.PI) / 180
        const x1 = 18 + Math.cos(rad) * 10
        const y1 = 18 + Math.sin(rad) * 10
        const x2 = 18 + Math.cos(rad) * 14
        const y2 = 18 + Math.sin(rad) * 14
        return (
          <line
            key={deg}
            x1={x1}
            y1={y1}
            x2={x2}
            y2={y2}
            stroke="white"
            strokeWidth="2.5"
            strokeLinecap="round"
          />
        )
      })}
    </svg>
  )
}

function EyeIcon({ open }) {
  return open ? (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  ) : (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" />
      <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19" />
      <line x1="1" y1="1" x2="23" y2="23" />
    </svg>
  )
}

export default function Login() {
  const navigate = useNavigate()
  const [password, setPassword]     = useState("")
  const [visible, setVisible]       = useState(false)
  const [error, setError]           = useState(false)
  const [shaking, setShaking]       = useState(false)

  function handleSubmit(e) {
    e.preventDefault()
    if (password === PASSWORD) {
      localStorage.setItem("auth", "true")
      navigate("/home")
    } else {
      setError(true)
      setShaking(true)
      setTimeout(() => setShaking(false), 600)
    }
  }

  function handleChange(e) {
    setPassword(e.target.value)
    if (error) setError(false)
  }

  return (
    <div className="min-h-dvh w-full flex flex-col items-center justify-center px-6"
         style={{ backgroundColor: "#0A0A0F" }}>

      {/* ── Logo block ── */}
      <div className="flex flex-col items-center gap-3 mb-16">
        {/* Orange sun circle */}
        <div
          className="w-20 h-20 rounded-full flex items-center justify-center shadow-lg"
          style={{ backgroundColor: "#E8500A" }}
        >
          <SunIcon />
        </div>

        {/* Company name */}
        <p
          className="text-white text-center"
          style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "24px", fontWeight: 600, letterSpacing: "-0.3px", margin: 0 }}
        >
          Swadev Energies
        </p>

        {/* Subtitle */}
        <p
          className="text-center"
          style={{ fontSize: "12px", color: "rgba(255,255,255,0.35)", margin: 0 }}
        >
          Warehouse Management
        </p>
      </div>

      {/* ── Form ── */}
      <form onSubmit={handleSubmit} className="w-full max-w-sm flex flex-col gap-3">

        {/* Password input */}
        <div
          className="flex items-center rounded-2xl px-4 py-0 gap-2"
          style={{
            background: "rgba(255,255,255,0.05)",
            border: "1px solid rgba(255,255,255,0.08)",
          }}
        >
          <input
            type={visible ? "text" : "password"}
            value={password}
            onChange={handleChange}
            placeholder="Password"
            autoComplete="current-password"
            className="flex-1 bg-transparent outline-none text-white py-4 text-sm placeholder:text-white/30"
            style={{ fontFamily: "'DM Sans', sans-serif" }}
          />
          <button
            type="button"
            onClick={() => setVisible((v) => !v)}
            className="text-white/40 hover:text-white/70 transition-colors flex-shrink-0 p-1"
            aria-label={visible ? "Hide password" : "Show password"}
          >
            <EyeIcon open={visible} />
          </button>
        </div>

        {/* Error text */}
        <p
          className="text-center text-sm transition-all duration-200"
          style={{
            color: "#FF5A5A",
            minHeight: "20px",
            opacity: error ? 1 : 0,
            fontFamily: "'DM Sans', sans-serif",
          }}
        >
          {error ? "Galat password hai" : ""}
        </p>

        {/* Login button */}
        <button
          type="submit"
          className="w-full rounded-2xl py-4 text-white transition-transform active:scale-95"
          style={{
            backgroundColor: "#E8500A",
            fontFamily: "'DM Sans', sans-serif",
            fontSize: "15px",
            fontWeight: 600,
            border: "none",
            cursor: "pointer",
            animation: shaking ? "shake 0.6s ease" : "none",
          }}
        >
          Login karo
        </button>
      </form>

      {/* ── Shake keyframes ── */}
      <style>{`
        @keyframes shake {
          0%   { transform: translateX(0); }
          15%  { transform: translateX(-8px); }
          30%  { transform: translateX(8px); }
          45%  { transform: translateX(-6px); }
          60%  { transform: translateX(6px); }
          75%  { transform: translateX(-3px); }
          90%  { transform: translateX(3px); }
          100% { transform: translateX(0); }
        }
      `}</style>
    </div>
  )
}
