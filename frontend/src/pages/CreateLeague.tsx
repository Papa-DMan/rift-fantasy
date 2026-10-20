import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, fromLocalInput } from '../api'
import { ErrorNote, Stepper } from '../components/ui'
import { RosterSlotsEditor } from '../components/RosterSlotsEditor'

const DEFAULT_SLOTS = { top: 1, jungle: 1, mid: 1, adc: 1, support: 1, coach: 1, bench: 2 }

export default function CreateLeague() {
  const nav = useNavigate()
  const [name, setName] = useState('')
  const [teamName, setTeamName] = useState('')
  const [maxTeams, setMaxTeams] = useState(8)
  const [slots, setSlots] = useState<Record<string, number>>(DEFAULT_SLOTS)
  const [deadline, setDeadline] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const league = await api.createLeague({
        name: name.trim(), team_name: teamName.trim(), max_teams: maxTeams,
        roster_slots: slots, trade_deadline: fromLocalInput(deadline),
      })
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
        <div className="topbar-title">New league</div>
        <span style={{ width: 40 }} />
      </header>
      <main className="content">
        <form className="form" onSubmit={submit}>
          <div className="card form">
            <label>League name
              <input value={name} onChange={(e) => setName(e.target.value)} required maxLength={100} placeholder="Worlds 2026 with the boys" />
            </label>
            <label>Your team name
              <input value={teamName} onChange={(e) => setTeamName(e.target.value)} required maxLength={64} placeholder="Baron Steal Enjoyers" />
            </label>
            <div className="field-row">
              <span>Max teams</span>
              <Stepper label="teams" value={maxTeams} min={2} max={20} onChange={setMaxTeams} />
            </div>
          </div>
          <details className="card">
            <summary>Roster slots</summary>
            <RosterSlotsEditor value={slots} onChange={setSlots} />
          </details>
          <details className="card">
            <summary>Trade deadline</summary>
            <label>Trades close at (optional)
              <input type="datetime-local" value={deadline} onChange={(e) => setDeadline(e.target.value)} />
            </label>
          </details>
          <ErrorNote error={error} />
          <button className="btn btn-primary btn-block" disabled={busy}>{busy ? 'Creating…' : 'Create league'}</button>
          <p className="muted small center">You'll be the commissioner and get an invite code to share.</p>
        </form>
      </main>
    </div>
  )
}
