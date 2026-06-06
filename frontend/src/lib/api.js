const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000"

async function request(path) {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`)
  return res.json()
}

export const api = {
  products: ()      => request("/api/products"),
  stats:    ()      => request("/api/products/stats"),
  transactions: ()  => request("/api/transactions"),
}
