import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import { ErrorNote } from '../components/ui'

export default function JoinLeague() {
  const nav = useNavigate()
  const [params] = useSearchParams()
  const [code, setCode] = useState(() => (params.get('code') ?? '').toUpperCase())
  const [teamName, setTeamName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const league = await api.joinLeague(code.trim(), teamName.trim())
      nav(`/leagues/${league.id}`, { replace: true })
    } catch (err) {
      setError((err as Error).message)
      setBusy(false)
    }
  }

  return (
    <div className="page">
      <header className="topbar">
        <Link to="/" className="icon-btn" aria-label="Back">‹</Link>
        <div className="topbar-title">Join a league</div>
        <span style={{ width: 40 }} />
      </header>
      <main className="content">
        <form className="card form" onSubmit={submit}>
          <label>Invite code
            <input className="code-input" value={code} onChange={(e) => setCode(e.target.value.toUpperCase().replace(/\s/g, ''))}
              required maxLength={16} autoCapitalize="characters" autoComplete="off" spellCheck={false} placeholder="ABCD2345" />
          </label>
          <label>Your team name
            <input value={teamName} onChange={(e) => setTeamName(e.target.value)} required maxLength={64} />
          </label>
          <ErrorNote error={error} />
          <button className="btn btn-primary btn-block" disabled={busy}>{busy ? 'Joining…' : 'Join league'}</button>
        </form>
      </main>
    </div>
  )
}
