import { Link, useNavigate } from "react-router-dom"
import logo from "../assets/firs-logo.png"

export default function Navbar({ isAuth, onLogout, hideAuthButtons }) {
  const navigate = useNavigate()

  const handleLogout = () => {
    onLogout()
    navigate("/")
  }

  return (
    <nav style={styles.nav}>
      <div style={styles.left}>
        <img src={logo} alt="FIRS Logo" style={styles.logo} />
        <span style={styles.title}>Nigeria Tax Reform Assistant</span>
      </div>

      <div style={styles.right}>
        {!hideAuthButtons && !isAuth && (
          <>
            <Link to="/login">Login</Link>
            <Link to="/register">Register</Link>
          </>
        )}

        {isAuth && (
          <button onClick={handleLogout} style={styles.logout}>
            Logout
          </button>
        )}
      </div>
    </nav>
  )
}

const styles = {
  nav: {
    height: "70px",
    backgroundColor: "#0A5C36",
    color: "#fff",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "0 40px"
  },
  left: {
    display: "flex",
    alignItems: "center",
    gap: "12px"
  },
  logo: {
    height: "40px"
  },
  title: {
    fontWeight: "600",
    fontSize: "16px"
  },
  right: {
    display: "flex",
    gap: "20px",
    alignItems: "center"
  },
  logout: {
    background: "transparent",
    color: "#fff",
    border: "1px solid #fff",
    padding: "6px 14px",
    borderRadius: "6px",
    cursor: "pointer"
  }
}

