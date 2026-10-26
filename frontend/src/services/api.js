const API_ROOT = import.meta.env.VITE_API_URL || 'http://localhost:8000/api'
const TOKEN_KEY = 'actionlens_token'

export function getToken() { return localStorage.getItem(TOKEN_KEY) }
export function setToken(value) { value ? localStorage.setItem(TOKEN_KEY, value) : localStorage.removeItem(TOKEN_KEY) }

export async function request(path, options = {}) {
  const headers = new Headers(options.headers || {})
  const token = getToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  const response = await fetch(`${API_ROOT}${path}`, { ...options, headers })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`)
  return data
}

function uploadFile(form, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', `${API_ROOT}/notices/upload`)
    const token = getToken()
    if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`)
    xhr.upload.onprogress = (event) => { if (event.lengthComputable && onProgress) onProgress(Math.round(event.loaded / event.total * 100)) }
    xhr.onload = () => {
      let data = {}
      try { data = JSON.parse(xhr.responseText || '{}') } catch {}
      if (xhr.status >= 200 && xhr.status < 300) resolve(data)
      else reject(new Error(data.detail || `Upload failed (${xhr.status})`))
    }
    xhr.onerror = () => reject(new Error('The upload could not reach the API. Check your connection and try again.'))
    xhr.onabort = () => reject(new Error('Upload cancelled.'))
    xhr.send(form)
  })
}

export const api = {
  login: (body) => request('/auth/login', { method: 'POST', body: JSON.stringify(body) }),
  register: (body) => request('/auth/register', { method: 'POST', body: JSON.stringify(body) }),
  me: () => request('/auth/me'),
  stats: () => request('/dashboard/stats'),
  notices: (params = {}) => request(`/notices?${new URLSearchParams(params)}`),
  notice: (id) => request(`/notices/${id}`),
  upload: (form, onProgress) => uploadFile(form, onProgress),
  analyze: (body) => request('/notices/analyze', { method: 'POST', body: JSON.stringify(body) }),
  patchChecklist: (noticeId, itemId, completed) => request(`/checklists/${noticeId}/items/${itemId}`, { method: 'PATCH', body: JSON.stringify({ completed }) }),
  reminders: () => request('/reminders'),
  createReminder: (body) => request('/reminders', { method: 'POST', body: JSON.stringify(body) }),
  patchReminder: (id, enabled) => request(`/reminders/${id}`, { method: 'PATCH', body: JSON.stringify({ enabled }) }),
  deleteReminder: (id) => request(`/reminders/${id}`, { method: 'DELETE' }),
  question: (id, question) => request(`/notices/${id}/questions`, { method: 'POST', body: JSON.stringify({ question }) }),
  translate: (id, language) => request(`/notices/${id}/translate`, { method: 'POST', body: JSON.stringify({ language }) }),
  deleteNotice: (id) => request(`/notices/${id}`, { method: 'DELETE' }),
  preferences: () => request('/preferences'),
  savePreferences: (value) => request('/preferences', { method: 'PUT', body: JSON.stringify(value) }),
  adminStats: () => request('/admin/stats'),
}
