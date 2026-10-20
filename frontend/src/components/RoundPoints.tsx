import { useState } from 'react'
import { api, parseDate, type Round } from '../api'
import { useLoad } from '../hooks'
import { formatDateTime, formatPoints, SCORING_LABELS } from '../format'
import { Empty, ErrorNote, RoleBadge, Spinner } from './ui'

/** The round to show first: the live one, else the latest scored, else the next. */
function defaultRound(rounds: Round[]): Round | undefined {
  const scored = rounds.filter((r) => r.status === 'live' || r.status === 'final')
  return rounds.find((r) => r.status === 'live') ?? scored[scored.length - 1] ?? rounds.find((r) => r.status === 'upcoming')
}

function breakdownText(b: Record<string, number>) {
  return Object.entries(b).map(([k, v]) => `${SCORING_LABELS[k] ?? k} ${v > 0 ? '+' : ''}${formatPoints(v)}`).join(' · ')
}

export function RoundPoints({ leagueId, teamId, rounds }: { leagueId: number; teamId: number; rounds: Round[] }) {
  const shown = rounds.filter((r) => r.status !== 'before_draft')
  const [picked, setPicked] = useState<number | null>(null)
  const roundId = picked ?? defaultRound(shown)?.id ?? null
  const { data, error, loading, reload } = useLoad(
    () => roundId === null ? Promise.resolve(null) : api.teamRound(leagueId, teamId, roundId), [leagueId, teamId, roundId])

  if (!shown.length) return <Empty title="No rounds to score yet">Rounds that locked before your draft don't count.</Empty>
  const lockAt = parseDate(data?.round.lock_at)
  return (
    <section className="stack">
      <div className="chips scroll-x" role="tablist" aria-label="Rounds">
        {shown.map((r) => (
          <button key={r.id} className="chip-btn" aria-selected={r.id === roundId} onClick={() => setPicked(r.id)}>
            {r.name}{r.status === 'live' && <> <span className="live-dot" /></>}
          </button>
        ))}
      </div>
      <ErrorNote error={error} onRetry={() => reload()} />
      {loading && !data ? <Spinner /> : data && (
        <>
          <div className="round-total">
            <span className="muted small">
              {data.round.status === 'upcoming' ? `Locks ${formatDateTime(lockAt)} · current roster` : data.round.status === 'live' ? 'In progress' : 'Final'}
            </span>
            <span className="points">{formatPoints(data.total)}<span className="muted small"> pts</span></span>
          </div>
          <ul className="card list-plain slots">
            {data.lineup.map((s) => (
              <li key={`${s.slot}-${s.slot_index}`}>
                <span className="slot-label">{s.slot === 'bench' ? 'BN' : <RoleBadge role={s.slot} />}</span>
                <span className="grow">
                  <span className="player-name">{s.player.name}</span>
                  <span className="player-sub">
                    {s.player.team_code ?? 'Free agent'}
                    {data.round.status !== 'upcoming' && ` · ${s.games.length} game${s.games.length === 1 ? '' : 's'}`}
                  </span>
                  {s.games.map((g, i) => Object.keys(g.breakdown).length > 0 && (
                    <span key={g.game_id} className="breakdown" style={{ display: 'block' }}>
                      G{i + 1}: {breakdownText(g.breakdown)}
                    </span>
                  ))}
                </span>
                {data.round.status !== 'upcoming' && (
                  <span className={s.counts ? 'points' : 'points points-bench'} title={s.counts ? undefined : "Bench points don't count"}>
                    {formatPoints(s.points)}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  )
}
