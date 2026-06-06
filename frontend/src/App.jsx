import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom"
import Login from "./pages/Login"
import Home   from "./pages/Home"

function ProtectedRoute({ children }) {
  return localStorage.getItem("auth")
    ? children
    : <Navigate to="/login" replace />
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/"      element={<Navigate to="/login" replace />} />
        <Route path="/login" element={<Login />} />
        <Route path="/home"  element={<ProtectedRoute><Home /></ProtectedRoute>} />
        {/* More pages go here */}
      </Routes>
    </BrowserRouter>
  )
}

export default App
