import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom"
import Login      from "./pages/Login"
import Home       from "./pages/Home"
import Challan    from "./pages/Challan"
import StockIn    from "./pages/StockIn"
import StockCheck from "./pages/StockCheck"
import History    from "./pages/History"
import AddProduct from "./pages/AddProduct"

function ProtectedRoute({ children }) {
  return localStorage.getItem("auth")
    ? children
    : <Navigate to="/login" replace />
}

function P({ children }) {
  return <ProtectedRoute>{children}</ProtectedRoute>
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/"            element={<Navigate to="/login" replace />} />
        <Route path="/login"       element={<Login />} />
        <Route path="/home"        element={<P><Home /></P>} />
        <Route path="/challan"     element={<P><Challan /></P>} />
        <Route path="/stock-in"    element={<P><StockIn /></P>} />
        <Route path="/stock-check" element={<P><StockCheck /></P>} />
        <Route path="/history"     element={<P><History /></P>} />
        <Route path="/add-product" element={<P><AddProduct /></P>} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
