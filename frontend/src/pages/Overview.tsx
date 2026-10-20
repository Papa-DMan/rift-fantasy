import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, fromLocalInput, parseDate, SLOTS, toLocalInput, type Standings } from '../api'
import { useLeague } from '../league'
import { useLoad } from '../hooks'
import { ErrorNote, Sheet, Spinner, Stepper } from '../components/ui'
import { formatDateTime, formatPoints, ordinal, SCORING_LABELS } from '../format'
import { RosterSlotsEditor } from '../components/RosterSlotsEditor'

export default function Overview() {
  const { league, me, reloadLeague } = useLeague()
  const nav = useNavigate()
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const deadline = parseDate(league.trade_deadline)
  const drafted = league.status === 'active' || league.status === 'finished'
  const standings = useLoad(() => drafted ? api.standings(league.id) : Promise.resolve(null), [league.id, drafted, league.scoring_rules])

  const leave = async () => {
    if (!confirm(`Leave ${league.name}? Your team will be removed.`)) return
    try { await api.leaveLeague(league.id); nav('/', { replace: true }) } catch (e) { setError((e as Error).message) }
  }

  return (
    <div className="stack">
      <StatusCard standings={standings.data} />

      {league.invite_code && league.status === 'setup' && <InviteCard />}

      {drafted ? (
        <section>
          <h2 className="section-title">Standings</h2>
          <ErrorNote error={standings.error} onRetry={() => standings.reload()} />
          {standings.data ? <StandingsTable standings={standings.data} /> : !standings.error && <Spinner />}
        </section>
      ) : <section>
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
      </section>}

      <section>
        <h2 className="section-title">Rules</h2>
        <div className="card kv">
          <div><span>Tournament</span><span>{league.tournament_id}</span></div>
          <div><span>Roster</span><span>{SLOTS.filter((s) => (league.roster_slots[s] ?? 0) > 0).map((s) => `${league.roster_slots[s]} ${s}`).join(', ')}</span></div>
          <div><span>Trade deadline</span><span>{deadline ? formatDateTime(deadline) : 'None'}</span></div>
          <div><span>Scoring</span><span>{scoringSummary(league.scoring_rules)}</span></div>
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

function scoringSummary(rules: Record<string, number>) {
  return Object.keys(SCORING_LABELS).filter((k) => rules[k])
    .map((k) => `${SCORING_LABELS[k]} ${rules[k] > 0 ? '+' : ''}${formatPoints(rules[k])}`).join(' · ')
}

function StandingsTable({ standings }: { standings: Standings }) {
  const { me } = useLeague()
  const scored = standings.rounds.filter((r) => r.status === 'live' || r.status === 'final')
  const last = scored[scored.length - 1]
  return (
    <ul className="card list-plain">
      {standings.teams.map((t, i) => (
        <li key={t.team_id}>
          <Link to={`roster/${t.team_id}`} className="row-link">
            <span className="rank">{i + 1}</span>
            <span className="grow">
              {t.name}
              {t.team_id === me.id && <span className="tag">You</span>}
              {last && <span className="player-sub">{last.name}: {formatPoints(t.rounds[last.id] ?? 0)}{last.status === 'live' ? ' so far' : ''}</span>}
            </span>
            <span className="points">{formatPoints(t.total)}<span className="muted small"> pts</span></span>
          </Link>
        </li>
      ))}
    </ul>
  )
}

function StatusCard({ standings }: { standings?: Standings | null }) {
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
    default: {
      const rank = standings ? standings.teams.findIndex((t) => t.team_id === me.id) : -1
      const mine = rank >= 0 ? standings!.teams[rank] : null
      const live = standings?.rounds.find((r) => r.status === 'live')
      const next = standings?.rounds.find((r) => r.status === 'upcoming')
      const lockAt = parseDate(next?.lock_at)
      return (
        <div className={`card hero-card${live ? ' hero-live' : ''}`}>
          <div className="hero-kicker">
            {live ? <><span className="live-dot" /> {live.name} is live</> : league.status === 'active' ? 'Season underway' : 'Season over'}
          </div>
          <div className="hero-title">{me.name}</div>
          {mine && <div className="hero-stat">{formatPoints(mine.total)} pts · {ordinal(rank + 1)} of {standings!.teams.length}</div>}
          <p className="muted">
            {next && lockAt
              ? `Lineups lock for ${next.name} ${formatDateTime(lockAt)}. Your starters are whoever fills each slot on your roster then.`
              : 'Only starters score; bench players don\'t count.'}
          </p>
          <div className="action-row">
            <Link to={`roster/${me.id}`} className="btn btn-primary">My roster</Link>
            <Link to="trades" className="btn btn-secondary">Trades</Link>
          </div>
        </div>
      )
    }
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
  const [rules, setRules] = useState<Record<string, string>>(
    () => Object.fromEntries(Object.keys(SCORING_LABELS).map((k) => [k, String(league.scoring_rules[k] ?? 0)])))
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const locked = league.status !== 'setup'

  const save = async () => {
    setBusy(true)
    setError(null)
    try {
      const scoring_rules = Object.fromEntries(Object.entries(rules).map(([k, v]) => [k, Number(v) || 0]))
      await api.updateLeague(league.id, {
        name: name.trim(), trade_deadline: fromLocalInput(deadline), scoring_rules,
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
      <div className="field-label">Points per stat</div>
      <div className="rules-editor">
        {Object.keys(SCORING_LABELS).map((k) => (
          <label key={k} className="rules-row">
            <span>{SCORING_LABELS[k]}</span>
            <input type="number" inputMode="decimal" step="any" value={rules[k]}
              onChange={(e) => setRules({ ...rules, [k]: e.target.value })} />
          </label>
        ))}
      </div>
      <p className="muted small">CS, vision, damage and gold are points per unit (0.02 per CS is 1 point per 50 CS). Changes apply to every round, past ones included.</p>
      <ErrorNote error={error} />
      <button className="btn btn-primary btn-block" onClick={save} disabled={busy}>{busy ? 'Saving…' : 'Save'}</button>
    </div>
  )
}
