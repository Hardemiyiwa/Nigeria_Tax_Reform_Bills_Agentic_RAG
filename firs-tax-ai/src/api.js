const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000"

async function request(path, { method = "GET", body, token } = {}) {
  const headers = { "Content-Type": "application/json" }
  if (token) headers["Authorization"] = `Bearer ${token}`

  const res = await fetch(`${API_URL}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  })

  const data = await res.json()
  if (!res.ok) throw new Error(data.detail || data.message || "Request failed")
  return data
}

export async function login(email, password) {
  return request("/auth/login", { method: "POST", body: { email, password } })
}

export async function signup(email, password) {
  return request("/auth/signup", { method: "POST", body: { email, password } })
}

export async function sendChat(message, chat_id = null, token, language = null) {
  const body = { message, chat_id }
  if (language) body.language = language
  return request("/chat", {
    method: "POST",
    body,
    token,
  })
}

export async function listChats(token) {
  return request("/chats", { method: "GET", token })
}

export async function getChatMessages(chat_id, token) {
  return request(`/chats/${chat_id}`, { method: "GET", token })
}

export default { API_URL, request, login, signup, sendChat, listChats, getChatMessages }
