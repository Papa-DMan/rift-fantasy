import { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api, parseDate, type Player, type Trade } from '../api'
import { useInterval, useLoad, useVisible } from '../hooks'
import { useLeague } from '../league'
import { rosterFits } from '../roster'
import { Empty, ErrorNote, PlayerLine, Sheet, Spinner, StatusChip } from '../components/ui'
import { formatDateTime } from '../format'

type View = 'inbox' | 'sent' | 'all'

export default function TradesPage() {
  const { league, me } = useLeague()
  const [params, setParams] = useSearchParams()
  const withTeam = params.get('with')
  const [view, setView] = useState<View>('inbox')
  const visible = useVisible()
  const trades = useLoad(() => api.trades(league.id), [league.id])
  useInterval(() => trades.reload(true), visible ? 20000 : null)

  const deadline = parseDate(league.trade_deadline)
  const closedReason = league.status !== 'active' ? (league.status === 'finished' ? 'The season is over.' : 'Trading opens after the draft.')
    : deadline && deadline.getTime() < Date.now() ? 'The trade deadline has passed.' : null

  const list = useMemo(() => {
    const all = trades.data ?? []
    if (view === 'inbox') return all.filter((t) => t.status === 'proposed' && t.receiver_team_id === me.id)
    if (view === 'sent') return all.filter((t) => t.status === 'proposed' && t.proposer_team_id === me.id)
    return all
  }, [trades.data, view, me.id])
  const inboxCount = trades.data?.filter((t) => t.status === 'proposed' && t.receiver_team_id === me.id).length ?? 0

  const closeSheet = () => { params.delete('with'); setParams(params, { replace: true }) }

  return (
    <div className="stack">
      {closedReason ? <div className="note">{closedReason}</div> : (
        <button className="btn btn-primary btn-block" onClick={() => setParams({ with: '' })}>Propose a trade</button>
      )}
      {!closedReason && deadline && <p className="muted small center">Trades close {formatDateTime(deadline)}</p>}

      <div className="segmented">
        <button aria-selected={view === 'inbox'} onClick={() => setView('inbox')}>Inbox{inboxCount > 0 && <span className="badge">{inboxCount}</span>}</button>
        <button aria-selected={view === 'sent'} onClick={() => setView('sent')}>Sent</button>
        <button aria-selected={view === 'all'} onClick={() => setView('all')}>League</button>
      </div>

      <ErrorNote error={trades.error} onRetry={() => trades.reload()} />
      {trades.loading && !trades.data ? <Spinner /> : list.length === 0 ? (
        <Empty title={view === 'inbox' ? 'No offers waiting on you' : view === 'sent' ? 'No open offers from you' : 'No trades yet'} />
      ) : (
        <ul className="list">
          {list.map((t) => <li key={t.id}><TradeCard trade={t} onChange={() => trades.reload(true)} /></li>)}
        </ul>
      )}

      <Sheet open={withTeam !== null && !closedReason} onClose={closeSheet} title="Propose a trade">
        <ProposeForm initialTeam={withTeam ? Number(withTeam) : null} onDone={() => { closeSheet(); setView('sent'); trades.reload(true) }} />
      </Sheet>
    </div>
  )
}

function TradeCard({ trade, onChange }: { trade: Trade; onChange: () => void }) {
  const { league, me, teamsById, playersById, reloadPlayers } = useLeague()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const proposer = teamsById.get(trade.proposer_team_id)
  const receiver = teamsById.get(trade.receiver_team_id)
  const gives = trade.items.filter((i) => i.from_team_id === trade.proposer_team_id)
  const gets = trade.items.filter((i) => i.from_team_id === trade.receiver_team_id)
  const open = trade.status === 'proposed'
  const created = parseDate(trade.created_at)

  const act = async (action: 'accept' | 'reject' | 'cancel') => {
    if (action === 'accept' && !confirm('Accept this trade? Players swap right away.')) return
    setBusy(true)
    setError(null)
    try {
      await api.tradeAction(league.id, trade.id, action)
      if (action === 'accept') await reloadPlayers()
      onChange()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const side = (title: string, items: typeof gives) => (
    <div className="trade-side">
      <div className="trade-side-title">{title}</div>
      {items.map((i) => <PlayerLine key={i.player_id} player={playersById.get(i.player_id)} />)}
    </div>
  )

  return (
    <div className="card trade">
      <div className="trade-head">
        <div className="small">
          <strong>{proposer?.name}</strong> <span className="muted">→</span> <strong>{receiver?.name}</strong>
          {created && <div className="muted">{formatDateTime(created)}</div>}
        </div>
        <StatusChip status={trade.status} />
      </div>
      {side(`${proposer?.name} sends`, gives)}
      {side(`${receiver?.name} sends`, gets)}
      {trade.message && <blockquote className="trade-msg">“{trade.message}”</blockquote>}
      <ErrorNote error={error} />
      {open && trade.receiver_team_id === me.id && (
        <div className="action-row">
          <button className="btn btn-primary" disabled={busy} onClick={() => act('accept')}>Accept</button>
          <button className="btn btn-ghost" disabled={busy} onClick={() => act('reject')}>Decline</button>
        </div>
      )}
      {open && trade.proposer_team_id === me.id && (
        <button className="btn btn-ghost btn-block" disabled={busy} onClick={() => act('cancel')}>Withdraw offer</button>
      )}
    </div>
  )
}

function ProposeForm({ initialTeam, onDone }: { initialTeam: number | null; onDone: () => void }) {
  const { league, me } = useLeague()
  const others = league.teams.filter((t) => t.id !== me.id)
  const [partner, setPartner] = useState<number | null>(initialTeam && others.some((t) => t.id === initialTeam) ? initialTeam : null)
  const [give, setGive] = useState<Set<number>>(new Set())
  const [receive, setReceive] = useState<Set<number>>(new Set())
  const [message, setMessage] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const mine = useLoad(() => api.roster(league.id, me.id), [league.id, me.id])
  const theirs = useLoad(() => (partner ? api.roster(league.id, partner) : Promise.resolve(null)), [league.id, partner])

  const myPlayers = mine.data?.players.map((e) => e.player) ?? []
  const theirPlayers = theirs.data?.players.map((e) => e.player) ?? []
  const after = (keep: Player[], out: Set<number>, incoming: Player[], inSet: Set<number>) =>
    [...keep.filter((p) => !out.has(p.id)), ...incoming.filter((p) => inSet.has(p.id))]
  const ready = partner && give.size > 0 && receive.size > 0
  const myFits = rosterFits(after(myPlayers, give, theirPlayers, receive), league.roster_slots)
  const theirFits = rosterFits(after(theirPlayers, receive, myPlayers, give), league.roster_slots)

  const toggle = (set: Set<number>, setter: (s: Set<number>) => void, id: number) => {
    const n = new Set(set)
    if (n.has(id)) n.delete(id)
    else if (n.size < 5) n.add(id)
    setter(n)
  }

  const submit = async () => {
    if (!partner) return
    setBusy(true)
    setError(null)
    try {
      await api.proposeTrade(league.id, {
        receiver_team_id: partner, give_player_ids: [...give], receive_player_ids: [...receive],
        message: message.trim() || undefined,
      })
      onDone()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const pickList = (players: Player[], set: Set<number>, setter: (s: Set<number>) => void) => (
    <ul className="card list-plain">
      {players.map((p) => (
        <li key={p.id}>
          <label className="check-row">
            <input type="checkbox" checked={set.has(p.id)} onChange={() => toggle(set, setter, p.id)} />
            <PlayerLine player={p} />
          </label>
        </li>
      ))}
    </ul>
  )

  return (
    <div className="form">
      <div className="field-label">Trade with</div>
      <div className="chips">
        {others.map((t) => (
          <button key={t.id} className="chip-btn" aria-selected={partner === t.id}
            onClick={() => { setPartner(t.id); setReceive(new Set()) }}>{t.name}</button>
        ))}
      </div>
      {partner && (
        <>
          <div className="field-label">You send</div>
          {mine.loading && !mine.data ? <Spinner /> : pickList(myPlayers, give, setGive)}
          <div className="field-label">You get</div>
          {theirs.loading && !theirs.data ? <Spinner /> : pickList(theirPlayers, receive, setReceive)}
          <label>Message (optional)
            <textarea value={message} onChange={(e) => setMessage(e.target.value)} maxLength={500} rows={2} placeholder="Sell them on it" />
          </label>
          {ready && (!myFits || !theirFits) && (
            <div className="note">{!myFits ? "Your roster wouldn't have room for that." : "Their roster wouldn't have room for that."} Uneven trades need open bench spots.</div>
          )}
        </>
      )}
      <ErrorNote error={error ?? mine.error ?? theirs.error} />
      <button className="btn btn-primary btn-block btn-lg" disabled={!ready || busy || !myFits || !theirFits} onClick={submit}>
        {busy ? 'Sending…' : 'Send offer'}
      </button>
    </div>
  )
}
