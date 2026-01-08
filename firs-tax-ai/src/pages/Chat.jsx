import { useState } from "react"
import Navbar from "../components/Navbar"
import "../styles/chat.css"
import { sendChat } from "../api"

export default function Chat({ onLogout }) {
  const [messages, setMessages] = useState([
    { role: "assistant", content: "Ask me anything about Nigeria’s tax reform." },
  ])
  const [input, setInput] = useState("")
  const [chatId, setChatId] = useState(null)

  const handleSend = async () => {
    if (!input.trim()) return
    const token = localStorage.getItem("token")

    const userMessage = { role: "user", content: input }
    setMessages((m) => [...m, userMessage])
    setInput("")

    try {
      const res = await sendChat(input, chatId, token)
      if (res.chat_id) setChatId(res.chat_id)
      setMessages((m) => [...m, { role: "assistant", content: res.reply }])
    } catch (err) {
      alert(err.message)
    }
  }

  return (
    <>
      <Navbar isAuth={true} onLogout={onLogout} />

      <div className="chat-layout">
        <aside className="chat-sidebar">
          <button className="new-chat-btn" onClick={() => { setChatId(null); setMessages([]) }}>＋ New Chat</button>

          <ul className="chat-list">
            <li className="active">VAT Reform Question</li>
          </ul>
        </aside>

        <main className="chat-main">
          <div className="chat-messages">
            {messages.map((m, i) => (
              <div key={i} className={`message ${m.role}`}>
                {m.content}
              </div>
            ))}
          </div>

          <div className="chat-input">
            <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="Type your question…" />
            <button className="send-btn" onClick={handleSend}>Send</button>
          </div>
        </main>
      </div>
    </>
  )
}
