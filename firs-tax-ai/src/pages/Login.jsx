import { useState } from "react"
import { useNavigate, Link } from "react-router-dom"
import Navbar from "../components/Navbar"
import "../styles/auth.css"
import { login } from "../api"

export default function Login({ onLogin }) {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const navigate = useNavigate()

  const handleSubmit = (e) => {
    e.preventDefault()
    console.log("Login submit", { email })
    ;(async () => {
      try {
        const res = await login(email, password)
        console.log("Login response", res)
        const token = res.access_token
        onLogin(token)
        navigate("/chat")
      } catch (err) {
        console.error("Login error", err)
        alert(err.message || String(err))
      }
    })()
  }

  return (
    <>
      <Navbar hideAuthButtons />

      <div className="auth-container">
        <h2>Login</h2>

        <form onSubmit={handleSubmit}>
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />

          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />

          <button type="submit">Login</button>
        </form>

        <p className="auth-switch">
          Don’t have an account? <Link to="/register">Register</Link>
        </p>
      </div>
    </>
  )
}

