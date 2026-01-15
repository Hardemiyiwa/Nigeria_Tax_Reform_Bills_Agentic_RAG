const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000"

async function request(path, { method = "GET", body, token } = {}) {
  const headers = { "Content-Type": "application/json" }
  if (token) headers["Authorization"] = `Bearer ${token}`

  const res = await fetch(`${API_URL}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  })
  console.log(`API Request -> ${method} ${API_URL}${path}`, { body, token })

  let data = null
  try {
    // some error responses may not be JSON; guard against that
    data = await res.json()
  } catch (err) {
    // if no JSON, capture text
    try {
      const txt = await res.text()
      data = { message: txt }
    } catch (e) {
      data = { message: "No response body" }
    }
  }

  if (!res.ok) {
    const msg = data?.detail || data?.message || `Request failed (${res.status})`
    console.warn(`API Response NOT OK ${res.status}`, data)
    throw new Error(msg)
  }

  console.log(`API Response OK ${res.status}`, data)
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

export async function calculateTax(grossIncome, purchaseAmount, taxType = "vat", token) {
  const body = { gross_income: grossIncome, purchase_amount: purchaseAmount, tax_type: taxType }
  return request("/calculator", { method: "POST", body, token })
}

export async function exportChat(chat_id, token, format = "pdf") {
  const res = await fetch(`${API_URL}/chats/${chat_id}/export`, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${token}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ chat_id, format })
  })
  
  if (format === "pdf") {
    // Handle PDF response as blob
    const blob = await res.blob()
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = `chat_${chat_id}.pdf`
    document.body.appendChild(a)
    a.click()
    window.URL.revokeObjectURL(url)
    document.body.removeChild(a)
    return { success: true }
  } else {
    const data = await res.json()
    return data
  }
}

export default { API_URL, request, login, signup, sendChat, listChats, getChatMessages, calculateTax, exportChat }
