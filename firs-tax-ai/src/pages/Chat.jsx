import { useEffect, useState, useRef } from "react"
import Navbar from "../components/Navbar"
import "../styles/chat.css"
import { sendChat, listChats, getChatMessages, calculateTax, exportChat } from "../api"

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

  // Voice input state
  const [isListening, setIsListening] = useState(false)
  const [recognition, setRecognition] = useState(null)
  
  // Calculator modal state
  const [showCalculator, setShowCalculator] = useState(false)
  const [calcInput, setCalcInput] = useState({ grossIncome: "", purchaseAmount: "", taxType: "vat" })
  const [calcResult, setCalcResult] = useState(null)
  const [exporting, setExporting] = useState(false)

  // Initialize Web Speech API
  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (SpeechRecognition) {
      const recognizer = new SpeechRecognition()
      recognizer.continuous = false
      recognizer.interimResults = false
      recognizer.lang = language === "en" ? "en-NG" : "yo-NG"
      
      recognizer.onresult = (event) => {
        const transcript = event.results[0][0].transcript
        setInput((prev) => prev + (prev ? " " : "") + transcript)
        setIsListening(false)
      }
      
      recognizer.onerror = (event) => {
        console.error("Speech recognition error:", event.error)
        setIsListening(false)
      }
      
      setRecognition(recognizer)
    }
  }, [language])

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

  const handleVoiceInput = () => {
    if (!recognition) {
      alert("Speech recognition not supported in this browser")
      return
    }
    if (isListening) {
      recognition.stop()
      setIsListening(false)
    } else {
      recognition.start()
      setIsListening(true)
    }
  }

  const handleCalculate = async () => {
    if (!calcInput.grossIncome && !calcInput.purchaseAmount) {
      alert("Please enter an amount")
      return
    }
    
    try {
      const token = localStorage.getItem("token")
      const result = await calculateTax(
        calcInput.grossIncome ? parseFloat(calcInput.grossIncome) : null,
        calcInput.purchaseAmount ? parseFloat(calcInput.purchaseAmount) : null,
        calcInput.taxType,
        token
      )
      setCalcResult(result)
    } catch (err) {
      alert(err.message)
    }
  }

  const handleExport = async () => {
    if (!chatId) {
      alert("No chat to export")
      return
    }
    
    setExporting(true)
    try {
      const token = localStorage.getItem("token")
      await exportChat(chatId, token, "pdf")
    } catch (err) {
      alert("Export failed: " + err.message)
    } finally {
      setExporting(false)
    }
  }

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
        setMessages(res.messages.map((mm) => ({ role: mm.role, content: mm.content, created_at: mm.created_at, sources: mm.sources || res.sources })))
      } else {
        setMessages((m) => [...m, { role: "assistant", content: res.reply, created_at: new Date().toISOString(), sources: res.sources }])
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
              <div key={i}>
                <div className={`message-row ${m.role}`}>
                  <div className="avatar" aria-hidden>
                    <Avatar role={m.role} name={m.role === "user" ? "You" : "FIRS"} />
                  </div>
                  <div className={`message ${m.role}`}>
                    <div className="message-content">{m.content}</div>
                    {m.created_at && <div className="message-meta">{formatRelativeTime(m.created_at)}</div>}
                  </div>
                </div>
                {/* Display document sources if available */}
                {m.sources && m.sources.length > 0 && (
                  <div style={{ marginLeft: 48, marginTop: 8, paddingLeft: 12, borderLeft: '2px solid #0b8a5f' }}>
                    <div style={{ fontSize: 12, color: '#999', marginBottom: 6 }}>📄 Sources:</div>
                    {m.sources.map((src, idx) => (
                      <div key={idx} style={{ fontSize: 11, color: '#aaa', marginBottom: 4, paddingRight: 12 }}>
                        <strong>{src.document}</strong>: "{src.excerpt.slice(0, 80)}..."
                      </div>
                    ))}
                  </div>
                )}
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

          {/* Tax Calculator Modal */}
          {showCalculator && (
            <div style={{
              position: 'fixed',
              top: 0,
              left: 0,
              width: '100%',
              height: '100%',
              backgroundColor: 'rgba(0,0,0,0.7)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              zIndex: 1000
            }}>
              <div style={{
                backgroundColor: '#0f1724',
                borderRadius: 8,
                padding: 24,
                width: 420,
                maxHeight: '80vh',
                overflowY: 'auto',
                border: '1px solid rgba(255,255,255,0.1)'
              }}>
                <h2 style={{ color: '#e6eef8', marginTop: 0 }}>💰 Tax Calculator</h2>
                <p style={{ color: '#aaa', fontSize: 13 }}>Calculate your Nigerian tax liability</p>

                <div style={{ marginBottom: 16 }}>
                  <label style={{ color: '#e6eef8', display: 'block', marginBottom: 6, fontSize: 12 }}>Tax Type</label>
                  <select value={calcInput.taxType} onChange={(e) => setCalcInput({ ...calcInput, taxType: e.target.value })} style={{
                    width: '100%',
                    padding: '8px 10px',
                    backgroundColor: '#16323a',
                    color: '#e6eef8',
                    border: '1px solid rgba(255,255,255,0.1)',
                    borderRadius: 4,
                    fontSize: 12,
                    boxSizing: 'border-box'
                  }}>
                    <option value="vat">VAT (7.5%)</option>
                    <option value="income_tax">Personal Income Tax</option>
                    <option value="cit">Corporate Income Tax (30%)</option>
                  </select>
                </div>

                {(calcInput.taxType === 'vat') && (
                  <div style={{ marginBottom: 16 }}>
                    <label style={{ color: '#e6eef8', display: 'block', marginBottom: 6, fontSize: 12 }}>Purchase Amount (₦)</label>
                    <input type="number" placeholder="100000" value={calcInput.purchaseAmount} onChange={(e) => setCalcInput({ ...calcInput, purchaseAmount: e.target.value })} style={{
                      width: '100%',
                      padding: '8px 10px',
                      backgroundColor: '#16323a',
                      color: '#e6eef8',
                      border: '1px solid rgba(255,255,255,0.1)',
                      borderRadius: 4,
                      fontSize: 12,
                      boxSizing: 'border-box'
                    }} />
                  </div>
                )}

                {(calcInput.taxType === 'income_tax' || calcInput.taxType === 'cit') && (
                  <div style={{ marginBottom: 16 }}>
                    <label style={{ color: '#e6eef8', display: 'block', marginBottom: 6, fontSize: 12 }}>Gross Amount (₦)</label>
                    <input type="number" placeholder="500000" value={calcInput.grossIncome} onChange={(e) => setCalcInput({ ...calcInput, grossIncome: e.target.value })} style={{
                      width: '100%',
                      padding: '8px 10px',
                      backgroundColor: '#16323a',
                      color: '#e6eef8',
                      border: '1px solid rgba(255,255,255,0.1)',
                      borderRadius: 4,
                      fontSize: 12,
                      boxSizing: 'border-box'
                    }} />
                  </div>
                )}

                <button onClick={handleCalculate} style={{
                  width: '100%',
                  padding: '10px',
                  backgroundColor: '#0b8a5f',
                  color: '#fff',
                  border: 'none',
                  borderRadius: 4,
                  cursor: 'pointer',
                  fontWeight: 'bold',
                  marginBottom: 12
                }}>Calculate</button>

                {calcResult && (
                  <div style={{
                    backgroundColor: '#16323a',
                    padding: 12,
                    borderRadius: 4,
                    marginBottom: 12,
                    border: '1px solid #0b8a5f'
                  }}>
                    <div style={{ color: '#0b8a5f', fontWeight: 'bold', marginBottom: 8 }}>{calcResult.tax_type}</div>
                    <div style={{ color: '#aaa', fontSize: 12, marginBottom: 4 }}>Gross: ₦{calcResult.gross_amount.toLocaleString()}</div>
                    <div style={{ color: '#aaa', fontSize: 12, marginBottom: 4 }}>Tax: ₦{calcResult.tax_amount.toLocaleString()} ({(calcResult.tax_rate * 100).toFixed(2)}%)</div>
                    <div style={{ color: '#0b8a5f', fontSize: 12, fontWeight: 'bold' }}>Net: ₦{calcResult.net_amount.toLocaleString()}</div>
                  </div>
                )}

                <button onClick={() => { setShowCalculator(false); setCalcResult(null) }} style={{
                  width: '100%',
                  padding: '8px',
                  backgroundColor: 'transparent',
                  color: '#e6eef8',
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: 4,
                  cursor: 'pointer'
                }}>Close</button>
              </div>
            </div>
          )}

          <div className="chat-input" style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
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
            <button onClick={handleVoiceInput} style={{
              padding: '8px 12px',
              backgroundColor: isListening ? '#ff6b6b' : '#16323a',
              color: '#e6eef8',
              border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: 4,
              cursor: 'pointer',
              fontSize: 16
            }} title={isListening ? "Stop listening" : "Start voice input (Shift+Microphone)"}>{isListening ? '🎙️' : '🎤'}</button>
            <button onClick={() => setShowCalculator(true)} style={{
              padding: '8px 12px',
              backgroundColor: '#16323a',
              color: '#e6eef8',
              border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: 4,
              cursor: 'pointer',
              fontSize: 16
            }} title="Tax calculator">💰</button>
            <button onClick={handleExport} disabled={!chatId || exporting} style={{
              padding: '8px 12px',
              backgroundColor: !chatId || exporting ? '#333' : '#16323a',
              color: '#e6eef8',
              border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: 4,
              cursor: !chatId || exporting ? 'not-allowed' : 'pointer',
              fontSize: 16,
              opacity: !chatId || exporting ? 0.5 : 1
            }} title="Export as PDF">📥</button>
            <button className="send-btn" onClick={handleSend} aria-label="Send">↑</button>
          </div>
        </main>
      </div>
    </>
  )
}
