import { useState } from "react"
import { useNavigate, Link } from "react-router-dom"
import Navbar from "../components/Navbar"
import "../styles/auth.css"
import { signup } from "../api"

export default function Register() {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const navigate = useNavigate()

  const handleSubmit = (e) => {
    e.preventDefault()
    ;(async () => {
      try {
        await signup(email, password)
        navigate("/login")
      } catch (err) {
        alert(err.message)
      }
    })()
  }

  return (
    <>
      <Navbar hideAuthButtons />

      <div className="auth-container">
        <h2>Create Account</h2>

        <form onSubmit={handleSubmit}>
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />

          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />

          <button type="submit">Register</button>
        </form>

        <p className="auth-switch">
          Already have an account? <Link to="/login">Login</Link>
        </p>
      </div>
    </>
  )
}
