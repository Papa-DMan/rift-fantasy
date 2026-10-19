import { useState, type FormEvent } from 'react'
import { useAuth } from '../auth'
import { ErrorNote } from '../components/ui'
import { InstallPrompt } from '../components/InstallPrompt'

export default function AuthPage() {
  const { login, register } = useAuth()
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      if (mode === 'login') await login(email.trim(), password)
      else await register(email.trim(), password, name.trim())
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth">
      <div className="auth-hero">
        <img src="/icons/icon-192.png" alt="" width={72} height={72} />
        <h1>Rift Fantasy</h1>
        <p className="muted">Draft pros, trade with friends, talk trash all Worlds long.</p>
      </div>
      <form className="card form" onSubmit={submit}>
        <div className="segmented" role="tablist">
          <button type="button" role="tab" aria-selected={mode === 'login'} onClick={() => setMode('login')}>Sign in</button>
          <button type="button" role="tab" aria-selected={mode === 'register'} onClick={() => setMode('register')}>Create account</button>
        </div>
        {mode === 'register' && (
          <label>Display name
            <input value={name} onChange={(e) => setName(e.target.value)} required maxLength={64} autoComplete="nickname" placeholder="What friends call you" />
          </label>
        )}
        <label>Email
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" inputMode="email" />
        </label>
        <label>Password
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required
            minLength={mode === 'register' ? 8 : undefined} maxLength={128}
            autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            placeholder={mode === 'register' ? 'At least 8 characters' : undefined} />
        </label>
        <ErrorNote error={error} />
        <button className="btn btn-primary btn-block" disabled={busy}>
          {busy ? 'One sec…' : mode === 'login' ? 'Sign in' : 'Create account'}
        </button>
      </form>
      <InstallPrompt />
    </div>
  )
}
