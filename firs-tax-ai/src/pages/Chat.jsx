import { useEffect, useState, useRef } from "react"
import Navbar from "../components/Navbar"
import "../styles/chat.css"
import { sendChat, listChats, getChatMessages } from "../api"

export default function Chat({ onLogout }) {
  const [messages, setMessages] = useState([
    { role: "assistant", content: "Ask me anything about Nigeria’s tax reform." },
  ])
  const [input, setInput] = useState("")
  const [chatId, setChatId] = useState(null)
  const [isTyping, setIsTyping] = useState(false)
  const [conversations, setConversations] = useState([])
  const messagesRef = useRef(null)
  const textareaRef = useRef(null)
  const [theme, setTheme] = useState(localStorage.getItem("theme") || "dark")
  const [language, setLanguage] = useState(localStorage.getItem("language") || "en")

  // auto-resize textarea
  useEffect(() => {
    const ta = textareaRef.current
    if (!ta) return
    ta.style.height = "auto"
    ta.style.height = `${Math.min(200, ta.scrollHeight)}px`
  }, [input])

  function formatRelativeTime(ts) {
    if (!ts) return ""
    const d = new Date(ts)
    const now = new Date()
    const diff = Math.floor((now - d) / 1000)
    if (diff < 5) return "just now"
    if (diff < 60) return `${diff}s`
    const m = Math.floor(diff / 60)
    if (m < 60) return `${m}m`
    const h = Math.floor(m / 60)
    if (h < 24) return `${h}h`
    const days = Math.floor(h / 24)
    return `${days}d`
  }

  function Avatar({ role, name }) {
    const letter = role === "assistant" ? "A" : "Y"
    const bg = role === "assistant" ? "#16323a" : "#0b8a5f"
    return (
      <svg width="40" height="40" viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg" className="avatar-svg">
        <rect width="40" height="40" rx="8" fill={bg} />
        <text x="50%" y="50%" dominantBaseline="middle" textAnchor="middle" fontFamily="Arial, Helvetica, sans-serif" fontSize="18" fill="#e6eef8">{letter}</text>
      </svg>
    )
  }

  useEffect(() => {
    // try to load conversations from backend, fall back to localStorage
    const token = localStorage.getItem("token")
    if (token) {
      listChats(token)
        .then((data) => {
          const rows = data.chats || []
          const mapped = rows.map((r) => ({ id: r.id, title: (r.last_message || "").slice(0,40) || `Chat ${r.id}`, lastMessage: r.last_message }))
          setConversations(mapped)
        })
        .catch(() => {
          const raw = localStorage.getItem("conversations")
          if (raw) setConversations(JSON.parse(raw))
        })
    } else {
      const raw = localStorage.getItem("conversations")
      if (raw) setConversations(JSON.parse(raw))
    }
  }, [])

  useEffect(() => {
    const el = messagesRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages, isTyping])

  useEffect(() => {
    if (theme === "light") document.body.classList.add("light")
    else document.body.classList.remove("light")
    localStorage.setItem("theme", theme)
  }, [theme])

  const handleSend = async () => {
    if (!input.trim()) return
    const token = localStorage.getItem("token")

    const userMessage = { role: "user", content: input }
    setMessages((m) => [...m, userMessage])
    setInput("")
    setIsTyping(true)

    try {
      const res = await sendChat(input, chatId, token, language)
      if (res.chat_id) setChatId(res.chat_id)
      // prefer messages returned by backend when available and include timestamps
      if (res.messages && Array.isArray(res.messages)) {
        setMessages(res.messages.map((mm) => ({ role: mm.role, content: mm.content, created_at: mm.created_at })))
      } else {
        setMessages((m) => [...m, { role: "assistant", content: res.reply, created_at: new Date().toISOString() }])
      }
      // persist conversation metadata
      try {
        const id = res.chat_id || chatId || `local_${Date.now()}`
        const updated = {
          id,
          title: input.slice(0, 40) || "New chat",
          lastMessage: res.reply,
        }
        const next = [updated, ...conversations.filter((c) => c.id !== id)]
        setConversations(next)
        localStorage.setItem("conversations", JSON.stringify(next))
      } catch (e) {
        // ignore local storage errors
      }
    } catch (err) {
      alert(err.message)
    } finally {
      setIsTyping(false)
    }
  }

  const startNewChat = () => {
    setChatId(null)
    setMessages([{ role: "assistant", content: "Ask me anything about Nigeria’s tax reform." }])
  }

  const openConversation = (conv) => {
    const token = localStorage.getItem("token")
    setChatId(conv.id)
    if (token) {
      getChatMessages(conv.id, token)
        .then((data) => {
          const msgs = (data.chat && data.chat.messages) || []
          setMessages(msgs.map((m) => ({ role: m.role, content: m.content, created_at: m.created_at })))
        })
        .catch(() => {
          // fallback
          setMessages([{ role: "assistant", content: conv.lastMessage || "" }])
        })
    } else {
      setMessages([{ role: "assistant", content: conv.lastMessage || "" }])
    }
  }

  return (
    <>
      <Navbar isAuth={true} onLogout={onLogout} />

      <div className="chat-layout">
        <aside className="chat-sidebar">
          <div style={{display:'flex', gap:8, alignItems:'center'}}>
            <button className="new-chat-btn" onClick={startNewChat}>＋ New Chat</button>
            <select value={language} onChange={(e)=>{ setLanguage(e.target.value); localStorage.setItem('language', e.target.value)}} style={{marginLeft:8, background:'#0f1724', color:'#e6eef8', border:'1px solid rgba(255,255,255,0.04)', padding:'6px 8px', borderRadius:6}}>
              <option value="en">EN</option>
              <option value="yo">Yor</option>
              <option value="ha">Hau</option>
              <option value="ig">Ibo</option>
              <option value="fr">FR</option>
            </select>
            <button onClick={()=>setTheme(theme==='dark'?'light':'dark')} style={{marginLeft:'auto', padding:'6px 10px', borderRadius:6, background:'transparent', color:'#e6eef8', border:'1px solid rgba(255,255,255,0.04)'}}>{theme==='dark'?'Light':'Dark'}</button>
          </div>

          <ul className="chat-list">
            {conversations.length === 0 && <li className="empty">No conversations yet</li>}
            {conversations.map((c) => (
              <li key={c.id} className={c.id === chatId ? "active" : ""} onClick={() => openConversation(c)}>
                <div className="chat-title">{c.title}</div>
                <div className="chat-last">{c.lastMessage?.slice(0, 60)}</div>
              </li>
            ))}
          </ul>
        </aside>

        <main className="chat-main">
          <div className="chat-messages" id="chatMessages" ref={messagesRef}>
            {messages.map((m, i) => (
              <div key={i} className={`message-row ${m.role}`}>
                <div className="avatar" aria-hidden>
                  <Avatar role={m.role} name={m.role === "user" ? "You" : "FIRS"} />
                </div>
                <div className={`message ${m.role}`}>
                  <div className="message-content">{m.content}</div>
                  {m.created_at && <div className="message-meta">{formatRelativeTime(m.created_at)}</div>}
                </div>
              </div>
            ))}

            {isTyping && (
              <div className="message-row assistant typing-row">
                <div className="avatar"><Avatar role="assistant" /></div>
                <div className="message assistant typing">
                  <span className="dot" />
                  <span className="dot" />
                  <span className="dot" />
                </div>
              </div>
            )}
          </div>

          <div className="chat-input">
            <textarea
              ref={textareaRef}
              className="chat-textarea"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Type your question… (Shift+Enter for newline)"
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault()
                  handleSend()
                }
              }}
            />
            <button className="send-btn" onClick={handleSend} aria-label="Send">↑</button>
          </div>
        </main>
      </div>
    </>
  )
}
