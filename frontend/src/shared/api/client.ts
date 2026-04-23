const API_BASE = '/api/v1'

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const url = `${API_BASE}${path}`
  const response = await fetch(url, {
    ...options,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: '请求失败' }))
    if (response.status === 401) {
      window.location.href = '/login'
    }
    const detail = error.detail
    let message: string
    if (Array.isArray(detail)) {
      message = detail.map((e: { msg?: string; message?: string }) => e.msg ?? e.message ?? JSON.stringify(e)).join('; ')
    } else if (typeof detail === 'string') {
      message = detail
    } else {
      message = `HTTP ${response.status}`
    }
    throw new Error(message)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return response.json()
}

export const api = {
  get: <T>(path: string) => request<T>(path, { method: 'GET' }),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'POST', body: body ? JSON.stringify(body) : undefined }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
}
