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
    console.log("Register submit", { email })
    ;(async () => {
      try {
        const res = await signup(email, password)
        console.log("Register response", res)
        navigate("/login")
      } catch (err) {
        console.error("Register error", err)
        alert(err.message || String(err))
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
