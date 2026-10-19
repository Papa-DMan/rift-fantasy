import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, fromLocalInput, parseDate, SLOTS, toLocalInput } from '../api'
import { useLeague } from '../league'
import { ErrorNote, Sheet, Stepper } from '../components/ui'
import { formatDateTime } from '../format'
import { RosterSlotsEditor } from '../components/RosterSlotsEditor'

export default function Overview() {
  const { league, me, reloadLeague } = useLeague()
  const nav = useNavigate()
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const deadline = parseDate(league.trade_deadline)

  const leave = async () => {
    if (!confirm(`Leave ${league.name}? Your team will be removed.`)) return
    try { await api.leaveLeague(league.id); nav('/', { replace: true }) } catch (e) { setError((e as Error).message) }
  }

  return (
    <div className="stack">
      <StatusCard />

      {league.invite_code && league.status === 'setup' && <InviteCard />}

      <section>
        <h2 className="section-title">Teams <span className="muted">{league.teams.length}/{league.max_teams}</span></h2>
        <ul className="card list-plain">
          {league.teams.map((t) => (
            <li key={t.id}>
              <Link to={`roster/${t.id}`} className="row-link">
                <span className="avatar">{t.name.slice(0, 1).toUpperCase()}</span>
                <span className="grow">
                  {t.name}
                  {t.id === me.id && <span className="tag">You</span>}
                  {t.is_commissioner && <span className="tag tag-gold">Commish</span>}
                </span>
                <span className="muted">›</span>
              </Link>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h2 className="section-title">Rules</h2>
        <div className="card kv">
          <div><span>Tournament</span><span>{league.tournament_id}</span></div>
          <div><span>Roster</span><span>{SLOTS.filter((s) => (league.roster_slots[s] ?? 0) > 0).map((s) => `${league.roster_slots[s]} ${s}`).join(', ')}</span></div>
          <div><span>Trade deadline</span><span>{deadline ? formatDateTime(deadline) : 'None'}</span></div>
        </div>
      </section>

      <ErrorNote error={error} />
      {me.is_commissioner && <button className="btn btn-secondary btn-block" onClick={() => setSettingsOpen(true)}>League settings</button>}
      {!me.is_commissioner && league.status === 'setup' && <button className="btn btn-danger-ghost btn-block" onClick={leave}>Leave league</button>}

      <Sheet open={settingsOpen} onClose={() => setSettingsOpen(false)} title="League settings">
        <SettingsForm onDone={async () => { await reloadLeague(); setSettingsOpen(false) }} />
      </Sheet>
    </div>
  )
}

function StatusCard() {
  const { league, me } = useLeague()
  const open = league.max_teams - league.teams.length
  switch (league.status) {
    case 'setup':
      return (
        <div className="card hero-card">
          <div className="hero-kicker">Pre-draft</div>
          <div className="hero-title">{open > 0 ? `Waiting on friends · ${open} spot${open === 1 ? '' : 's'} open` : 'League is full'}</div>
          <p className="muted">{me.is_commissioner ? 'Set the draft time and order, then start it when everyone is ready.' : 'The commissioner starts the draft when everyone is in.'}</p>
          <Link to="draft" className="btn btn-primary">{me.is_commissioner ? 'Set up the draft' : 'Draft details'}</Link>
        </div>
      )
    case 'drafting':
      return (
        <div className="card hero-card hero-live">
          <div className="hero-kicker"><span className="live-dot" /> Live now</div>
          <div className="hero-title">The draft is on</div>
          <Link to="draft" className="btn btn-primary">Go to draft room</Link>
        </div>
      )
    default:
      return (
        <div className="card hero-card">
          <div className="hero-kicker">{league.status === 'active' ? 'Season underway' : 'Season over'}</div>
          <div className="hero-title">{me.name}</div>
          <p className="muted">Scoring is coming soon. For now, check rosters and work some trades.</p>
          <div className="action-row">
            <Link to={`roster/${me.id}`} className="btn btn-primary">My roster</Link>
            <Link to="trades" className="btn btn-secondary">Trades</Link>
          </div>
        </div>
      )
  }
}

function InviteCard() {
  const { league, reloadLeague } = useLeague()
  const [copied, setCopied] = useState(false)
  const link = `${location.origin}/join?code=${league.invite_code}`
  const text = `Join my League of Legends fantasy league "${league.name}" on Rift Fantasy. Invite code: ${league.invite_code}`

  const share = async () => {
    if (navigator.share) {
      try { await navigator.share({ title: 'Rift Fantasy invite', text, url: link }); return } catch { /* cancelled */ }
    }
    try { await navigator.clipboard.writeText(`${text}\n${link}`); setCopied(true); setTimeout(() => setCopied(false), 2000) } catch { /* ignore */ }
  }

  const rotate = async () => {
    if (!confirm('Make a new code? The current one stops working.')) return
    await api.rotateInvite(league.id)
    await reloadLeague()
  }

  return (
    <div className="card invite">
      <div className="muted small">Invite code</div>
      <div className="invite-code">{league.invite_code}</div>
      <div className="action-row">
        <button className="btn btn-primary" onClick={share}>{copied ? 'Copied!' : 'Share invite'}</button>
        <button className="btn btn-ghost" onClick={rotate}>New code</button>
      </div>
    </div>
  )
}

function SettingsForm({ onDone }: { onDone: () => Promise<void> }) {
  const { league } = useLeague()
  const [name, setName] = useState(league.name)
  const [maxTeams, setMaxTeams] = useState(league.max_teams)
  const [slots, setSlots] = useState(league.roster_slots)
  const [deadline, setDeadline] = useState(toLocalInput(league.trade_deadline))
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const locked = league.status !== 'setup'

  const save = async () => {
    setBusy(true)
    setError(null)
    try {
      await api.updateLeague(league.id, {
        name: name.trim(), trade_deadline: fromLocalInput(deadline),
        ...(locked ? {} : { max_teams: maxTeams, roster_slots: slots }),
      })
      await onDone()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="form">
      <label>League name<input value={name} onChange={(e) => setName(e.target.value)} maxLength={100} /></label>
      <label>Trade deadline<input type="datetime-local" value={deadline} onChange={(e) => setDeadline(e.target.value)} /></label>
      {locked ? <p className="muted small">Team count and roster slots are locked once the draft starts.</p> : <>
        <div className="field-row"><span>Max teams</span><Stepper label="teams" value={maxTeams} min={Math.max(2, league.teams.length)} max={20} onChange={setMaxTeams} /></div>
        <div className="field-label">Roster slots</div>
        <RosterSlotsEditor value={slots} onChange={setSlots} />
      </>}
      <ErrorNote error={error} />
      <button className="btn btn-primary btn-block" onClick={save} disabled={busy}>{busy ? 'Saving…' : 'Save'}</button>
    </div>
  )
}
