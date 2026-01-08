import Navbar from "../components/Navbar"

export default function History() {
  return (
    <>
      <Navbar isAuth={true} />
      <div style={{ padding: "40px" }}>
        <h2>Question History</h2>
      </div>
    </>
  )
}
