import { useNavigate } from "react-router-dom"
import Navbar from "../components/Navbar"
import "../styles/landing.css"

export default function Landing() {
  const navigate = useNavigate()

  return (
    <>
      <Navbar hideAuthButtons />

      <main className="landing">
        <h1>Understand Nigeria’s Tax Reform Bills</h1>
        <p>
          Get clear, factual answers backed by official government documents.
        </p>

        <button
          className="cta-btn"
          onClick={() => navigate("/login")}
        >
          Get Started
        </button>
      </main>
    </>
  )
}
