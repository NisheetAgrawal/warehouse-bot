const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000"

// ── Local session helpers ─────────────────────────────────────────
export function getToken() {
  return localStorage.getItem("auth")
}

export function getName() {
  return localStorage.getItem("name") || "User"
}

export function isLoggedIn() {
  return !!localStorage.getItem("auth")
}

export function setAuth({ token, name }) {
  localStorage.setItem("auth", token)
  localStorage.setItem("name", name || "User")
}

export function logout() {
  localStorage.removeItem("auth")
  localStorage.removeItem("name")
}

// ── API calls ─────────────────────────────────────────────────────
async function post(path, body) {
  const res  = await fetch(`${BASE}${path}`, {
    method:  "POST",
    headers: { "Content-Type": "application/json" },
    body:    JSON.stringify(body),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.detail || `Error ${res.status}`)
  return data
}

export function login(username, password) {
  return post("/api/auth/login", { username, password })
}

export function register(username, name, password) {
  return post("/api/auth/register", { username, name, password })
}
