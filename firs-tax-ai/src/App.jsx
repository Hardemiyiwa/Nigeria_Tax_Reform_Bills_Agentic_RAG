import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom"
import { useState } from "react"

import Landing from "./pages/Landing"
import Login from "./pages/Login"
import Register from "./pages/Register"
import Chat from "./pages/Chat"
import History from "./pages/History"

function App() {
  const [token, setToken] = useState(localStorage.getItem("token"))

  const handleLogin = (jwt) => {
    localStorage.setItem("token", jwt)
    setToken(jwt)
  }

  const handleLogout = () => {
    localStorage.removeItem("token")
    setToken(null)
  }

  const Protected = ({ children }) => {
    if (!token) return <Navigate to="/" replace />
    return children
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Landing />} />

        <Route
          path="/login"
          element={<Login onLogin={handleLogin} />}
        />

        <Route path="/register" element={<Register />} />

        <Route
          path="/chat"
          element={
            <Protected>
              <Chat onLogout={handleLogout} />
            </Protected>
          }
        />

        <Route
          path="/history"
          element={
            <Protected>
              <History />
            </Protected>
          }
        />
      </Routes>
    </BrowserRouter>
  )
}

export default App
