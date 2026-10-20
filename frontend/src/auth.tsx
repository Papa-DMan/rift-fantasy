import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { api, setUnauthorizedHandler, tokenStore, type User } from './api'

interface AuthState {
  user: User | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, displayName: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(() => !!tokenStore.get())

  const logout = useCallback(() => { tokenStore.set(null); setUser(null) }, [])

  useEffect(() => {
    setUnauthorizedHandler(logout)
    if (tokenStore.get()) {
      api.me().then(setUser).catch(() => tokenStore.set(null)).finally(() => setLoading(false))
    }
    return () => setUnauthorizedHandler(null)
  }, [logout])

  const login = useCallback(async (email: string, password: string) => {
    const { access_token } = await api.login(email, password)
    tokenStore.set(access_token)
    setUser(await api.me())
  }, [])

  const register = useCallback(async (email: string, password: string, displayName: string) => {
    await api.register({ email, password, display_name: displayName })
    await login(email, password)
  }, [login])

  return <AuthContext.Provider value={{ user, loading, login, register, logout }}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth outside AuthProvider')
  return ctx
}
