import { useEffect, useState } from "react"
import { api } from "../lib/api"

/**
 * Fetches all products once and provides a search function.
 * Re-used by StockIn, StockCheck, and Challan.
 */
export function useProducts() {
  const [products, setProducts] = useState([])
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState(null)

  useEffect(() => {
    api.products()
      .then((data) => { setProducts(data); setLoading(false) })
      .catch((err)  => { setError(err.message); setLoading(false) })
  }, [])

  function search(query, limit = 8) {
    const q = query.trim().toLowerCase()
    if (q.length < 2) return []
    return products
      .filter((p) => {
        const hay = `${p.brand} ${p.spec || ""} ${p.type_ || ""} ${p.category || ""}`.toLowerCase()
        return q.split(" ").every((word) => hay.includes(word))
      })
      .slice(0, limit)
  }

  return { products, loading, error, search }
}
