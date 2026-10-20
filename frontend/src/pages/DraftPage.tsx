import { useEffect, useMemo, useRef, useState } from 'react'
import { api, fromLocalInput, parseDate, POSITIONS, toLocalInput, type Draft, type DraftType, type Player } from '../api'
import { useInterval, useLoad, useNow, useVisible } from '../hooks'
import { useLeague } from '../league'
import { rosterFits } from '../roster'
import { RosterSlots } from '../components/RosterSlots'
import { Empty, ErrorNote, PlayerLine, RoleBadge, Sheet, Spinner } from '../components/ui'
import { normRole, formatCountdown, formatDateTime } from '../format'

export default function DraftPage() {
  const { league, reloadLeague } = useLeague()
  const visible = useVisible()
  const { data: draft, setData: setDraft, error, loading, reload } = useLoad(() => api.draft(league.id), [league.id])

  // GET /draft also applies autopicks for expired clocks, so polling keeps the room moving.
  const pollMs = !visible || !draft ? null : draft.status === 'in_progress' ? 3000 : draft.status === 'scheduled' ? 10000 : null
  useInterval(() => reload(true), pollMs)

  // Keep the league header (status chip, tabs) in step with the draft.
  const lastStatus = useRef(draft?.status)
  useEffect(() => {
    if (draft && lastStatus.current && draft.status !== lastStatus.current) reloadLeague()
    lastStatus.current = draft?.status
  }, [draft, reloadLeague])

  if (loading && !draft) return <Spinner label="Loading draft" />
  if (!draft) return <ErrorNote error={error} onRetry={() => reload()} />

  return (
    <div className="stack">
      {draft.status === 'scheduled' && <PreDraft draft={draft} onChange={setDraft} />}
      {draft.status !== 'scheduled' && <DraftRoom draft={draft} onChange={setDraft} />}
    </div>
  )
}

const PICK_TIMES = [
  { s: 30, label: '30 sec' }, { s: 60, label: '1 min' }, { s: 90, label: '90 sec' }, { s: 120, label: '2 min' },
  { s: 300, label: '5 min' }, { s: 3600, label: '1 hour' }, { s: 8 * 3600, label: '8 hours (slow draft)' },
]

function pickTimeLabel(s: number) {
  return PICK_TIMES.find((p) => p.s === s)?.label ?? (s >= 3600 ? `${(s / 3600).toFixed(1)} hours` : s >= 60 ? `${Math.round(s / 60)} min` : `${s} sec`)
}

function PreDraft({ draft, onChange }: { draft: Draft; onChange: (d: Draft) => void }) {
  const { league, me, teamsById } = useLeague()
  const when = parseDate(draft.scheduled_for)
  const [type, setType] = useState<DraftType>(draft.type)
  const [seconds, setSeconds] = useState(draft.seconds_per_pick)
  const [scheduled, setScheduled] = useState(toLocalInput(draft.scheduled_for))
  const [customOrder, setCustomOrder] = useState(false)
  const [order, setOrder] = useState(() => league.teams.map((t) => t.id))
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const dirty = type !== draft.type || seconds !== draft.seconds_per_pick || scheduled !== toLocalInput(draft.scheduled_for)

  // Teams can join while the commissioner is looking at this screen.
  useEffect(() => {
    setOrder((o) => [...o.filter((id) => teamsById.has(id)), ...league.teams.map((t) => t.id).filter((id) => !o.includes(id))])
  }, [league.teams, teamsById])

  const run = async (label: string, fn: () => Promise<Draft>) => {
    setBusy(label)
    setError(null)
    try { onChange(await fn()) } catch (e) { setError((e as Error).message) } finally { setBusy(null) }
  }

  const move = (i: number, d: number) => setOrder((o) => {
    const n = [...o]
    ;[n[i], n[i + d]] = [n[i + d], n[i]]
    return n
  })

  return (
    <>
      <div className="card hero-card">
        <div className="hero-kicker">Draft</div>
        <div className="hero-title">{when ? formatDateTime(when) : 'Not scheduled yet'}</div>
        <p className="muted">
          {draft.type === 'snake' ? 'Snake' : 'Linear'} draft · {pickTimeLabel(draft.seconds_per_pick)} per pick · {draft.total_rounds} rounds.
          {' '}If your clock runs out, you get the best available player that fits.
        </p>
        {!me.is_commissioner && <p className="muted small">Keep this screen open; it updates when the commissioner starts the draft.</p>}
      </div>

      {me.is_commissioner && (
        <>
          <section className="card form">
            <h2 className="card-title">Draft settings</h2>
            <div className="segmented">
              <button type="button" aria-selected={type === 'snake'} onClick={() => setType('snake')}>Snake</button>
              <button type="button" aria-selected={type === 'linear'} onClick={() => setType('linear')}>Linear</button>
            </div>
            <label>Time per pick
              <select value={seconds} onChange={(e) => setSeconds(Number(e.target.value))}>
                {!PICK_TIMES.some((p) => p.s === seconds) && <option value={seconds}>{pickTimeLabel(seconds)}</option>}
                {PICK_TIMES.map((p) => <option key={p.s} value={p.s}>{p.label}</option>)}
              </select>
            </label>
            <label>Scheduled for
              <input type="datetime-local" value={scheduled} onChange={(e) => setScheduled(e.target.value)} />
            </label>
            <button className="btn btn-secondary btn-block" disabled={!dirty || !!busy}
              onClick={() => run('save', () => api.updateDraft(league.id, { type, seconds_per_pick: seconds, scheduled_for: fromLocalInput(scheduled) }))}>
              {busy === 'save' ? 'Saving…' : 'Save settings'}
            </button>
          </section>

          <section className="card form">
            <h2 className="card-title">Draft order</h2>
            <div className="segmented">
              <button type="button" aria-selected={!customOrder} onClick={() => setCustomOrder(false)}>Random</button>
              <button type="button" aria-selected={customOrder} onClick={() => setCustomOrder(true)}>Set it myself</button>
            </div>
            {customOrder && (
              <ol className="order-list">
                {order.map((id, i) => (
                  <li key={id}>
                    <span className="order-num">{i + 1}</span>
                    <span className="grow">{teamsById.get(id)?.name}</span>
                    <button className="icon-btn" disabled={i === 0} onClick={() => move(i, -1)} aria-label="Move up">↑</button>
                    <button className="icon-btn" disabled={i === order.length - 1} onClick={() => move(i, 1)} aria-label="Move down">↓</button>
                  </li>
                ))}
              </ol>
            )}
          </section>

          <ErrorNote error={error} />
          <button className="btn btn-primary btn-block btn-lg" disabled={!!busy || league.teams.length < 2}
            onClick={() => {
              if (dirty && !confirm('You have unsaved draft settings. Start anyway with the saved ones?')) return
              if (!confirm(`Start the draft now with ${league.teams.length} teams? New teams can't join after this.`)) return
              run('start', () => api.startDraft(league.id, customOrder ? order : undefined))
            }}>
            {busy === 'start' ? 'Starting…' : 'Start draft now'}
          </button>
          {league.teams.length < 2 && <p className="muted small center">You need at least two teams to draft.</p>}
        </>
      )}
    </>
  )
}

type RoomTab = 'players' | 'board' | 'mine'

function DraftRoom({ draft, onChange }: { draft: Draft; onChange: (d: Draft) => void }) {
  const { league, me, playersById } = useLeague()
  const live = draft.status === 'in_progress'
  const [tab, setTab] = useState<RoomTab>(live ? 'players' : 'board')
  const myTurn = live && draft.on_the_clock_team_id === me.id
  const myPlayers = draft.picks.filter((p) => p.team_id === me.id && p.player_id).map((p) => playersById.get(p.player_id!)).filter(Boolean) as Player[]

  // Buzz once when it becomes your turn (installed apps on Android support this).
  const wasMyTurn = useRef(myTurn)
  useEffect(() => {
    if (myTurn && !wasMyTurn.current) {
      navigator.vibrate?.([120, 60, 120])
      setTab('players')
    }
    wasMyTurn.current = myTurn
  }, [myTurn])

  return (
    <>
      {live ? <OnTheClock draft={draft} myTurn={myTurn} /> : (
        <div className="card hero-card">
          <div className="hero-kicker">Draft complete</div>
          <div className="hero-title">Rosters are set</div>
          <p className="muted">Trading is open until the deadline.</p>
        </div>
      )}
      <div className="segmented sticky-seg">
        {live && <button aria-selected={tab === 'players'} onClick={() => setTab('players')}>Players</button>}
        <button aria-selected={tab === 'board'} onClick={() => setTab('board')}>Board</button>
        <button aria-selected={tab === 'mine'} onClick={() => setTab('mine')}>My team</button>
      </div>
      {tab === 'players' && live && <PlayerPool draft={draft} myTurn={myTurn} myPlayers={myPlayers} onPicked={onChange} />}
      {tab === 'board' && <Board draft={draft} />}
      {tab === 'mine' && <RosterSlots players={myPlayers} slots={league.roster_slots} />}
    </>
  )
}

function OnTheClock({ draft, myTurn }: { draft: Draft; myTurn: boolean }) {
  const { teamsById, me } = useLeague()
  const now = useNow(250)
  const deadline = parseDate(draft.pick_deadline)
  const left = deadline ? deadline.getTime() - now : 0
  const team = draft.on_the_clock_team_id ? teamsById.get(draft.on_the_clock_team_id) : null
  const cur = draft.picks.find((p) => p.overall_pick === draft.current_pick)
  const teamsCount = teamsById.size
  // Picks until my next turn.
  const nextMine = draft.picks.find((p) => p.team_id === me.id && !p.player_id && p.overall_pick >= (draft.current_pick ?? 0))
  const until = nextMine && draft.current_pick ? nextMine.overall_pick - draft.current_pick : null
  const pct = deadline ? Math.max(0, Math.min(1, left / (draft.seconds_per_pick * 1000))) : 0

  return (
    <div className={`card clock ${myTurn ? 'clock-mine' : ''} ${left < 10000 ? 'clock-urgent' : ''}`}>
      <div className="clock-top">
        <div>
          <div className="hero-kicker">Round {cur?.round_number} · Pick {cur ? ((cur.overall_pick - 1) % teamsCount) + 1 : ''} · #{draft.current_pick}</div>
          <div className="hero-title">{myTurn ? "You're on the clock!" : `${team?.name ?? '…'} is picking`}</div>
          {!myTurn && until !== null && <div className="muted small">{until === 1 ? "You're up next" : `You pick in ${until} picks`}</div>}
        </div>
        <div className="clock-time" aria-live="off">{formatCountdown(left)}</div>
      </div>
      <div className="clock-bar"><span style={{ width: `${pct * 100}%` }} /></div>
    </div>
  )
}

function PlayerPool({ draft, myTurn, myPlayers, onPicked }: { draft: Draft; myTurn: boolean; myPlayers: Player[]; onPicked: (d: Draft) => void }) {
  const { league } = useLeague()
  const [position, setPosition] = useState<string>('')
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState<Player | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const pickedCount = draft.picks.filter((p) => p.player_id).length
  const pool = useLoad(() => api.players(league.id, { available: true, position: position || undefined }), [league.id, position, pickedCount])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return (pool.data ?? []).filter((p) => !q || p.name.toLowerCase().includes(q) || p.team_code?.toLowerCase().includes(q))
  }, [pool.data, query])

  const confirmPick = async () => {
    if (!selected) return
    setBusy(true)
    setError(null)
    try {
      onPicked(await api.pick(league.id, selected.id))
      setSelected(null)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <div className="filters">
        <input type="search" placeholder="Search players or teams" value={query} onChange={(e) => setQuery(e.target.value)} />
        <div className="chips" role="tablist">
          <button className="chip-btn" aria-selected={position === ''} onClick={() => setPosition('')}>All</button>
          {POSITIONS.map((p) => (
            <button key={p} className="chip-btn" aria-selected={position === p} onClick={() => setPosition(p)}>{p === 'adc' ? 'ADC' : p[0].toUpperCase() + p.slice(1)}</button>
          ))}
        </div>
      </div>
      <ErrorNote error={pool.error} onRetry={() => pool.reload()} />
      {pool.loading && !pool.data ? <Spinner /> : filtered.length === 0 ? <Empty title="No players here">Try another position or search.</Empty> : (
        <ul className="card list-plain">
          {filtered.map((p) => {
            const fits = rosterFits([...myPlayers, p], league.roster_slots)
            return (
              <li key={p.id} className={fits ? '' : 'dim'}>
                <PlayerLine player={p} sub={fits ? undefined : 'no room'} right={
                  <button className="btn btn-primary btn-sm" disabled={!myTurn || !fits} onClick={() => { setError(null); setSelected(p) }}>Draft</button>
                } />
              </li>
            )
          })}
        </ul>
      )}
      <Sheet open={!!selected} onClose={() => setSelected(null)} title="Confirm pick">
        {selected && (
          <div className="form">
            <div className="pick-confirm">
              <RoleBadge role={selected.role} />
              <div className="pick-confirm-name">{selected.name}</div>
              <div className="muted">{selected.team_code}</div>
            </div>
            <ErrorNote error={error} />
            <button className="btn btn-primary btn-block btn-lg" onClick={confirmPick} disabled={busy || !myTurn}>
              {busy ? 'Drafting…' : myTurn ? `Draft ${selected.name}` : 'Your clock ran out'}
            </button>
          </div>
        )}
      </Sheet>
    </>
  )
}

function Board({ draft }: { draft: Draft }) {
  const { teamsById, playersById, me } = useLeague()
  const teamOrder = draft.picks.filter((p) => p.round_number === 1).sort((a, b) => a.overall_pick - b.overall_pick).map((p) => p.team_id)
  const rounds = Array.from({ length: draft.total_rounds }, (_, i) => i + 1)
  const cell = new Map(draft.picks.map((p) => [`${p.round_number}:${p.team_id}`, p]))

  return (
    <div className="board-wrap card">
      <table className="board">
        <thead>
          <tr>
            <th className="board-rd">Rd</th>
            {teamOrder.map((id) => <th key={id} className={id === me.id ? 'board-me' : ''}>{teamsById.get(id)?.name}</th>)}
          </tr>
        </thead>
        <tbody>
          {rounds.map((r) => (
            <tr key={r}>
              <td className="board-rd">{r}</td>
              {teamOrder.map((id) => {
                const p = cell.get(`${r}:${id}`)
                const player = p?.player_id ? playersById.get(p.player_id) : undefined
                const current = p?.overall_pick === draft.current_pick
                return (
                  <td key={id} className={`${current ? 'board-current' : ''} ${id === me.id ? 'board-me' : ''}`}>
                    {player ? (
                      <div className={`board-cell role-bg-${normRole(player.role) ?? 'none'}`}>
                        <span className="board-name">{player.name}</span>
                        <span className="board-sub">{player.team_code}{p?.is_autopick && ' · auto'}</span>
                      </div>
                    ) : <div className="board-cell board-empty">{current ? 'On clock' : `#${p?.overall_pick ?? ''}`}</div>}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
