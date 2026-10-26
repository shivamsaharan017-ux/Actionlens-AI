import { createContext, useContext, useEffect, useState } from 'react'
import { api, getToken, setToken } from '../services/api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(Boolean(getToken()))
  useEffect(() => {
    if (!getToken()) return
    api.me().then(setUser).catch(() => setToken(null)).finally(() => setLoading(false))
  }, [])
  const signIn = async (credentials, create = false) => {
    const result = create ? await api.register(credentials) : await api.login(credentials)
    setToken(result.access_token); setUser(result.user); return result.user
  }
  const signOut = () => { setToken(null); setUser(null) }
  return <AuthContext.Provider value={{ user, loading, signIn, signOut }}>{children}</AuthContext.Provider>
}

export function useAuth() { return useContext(AuthContext) }
