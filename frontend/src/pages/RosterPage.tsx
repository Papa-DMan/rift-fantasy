import { Link, useParams } from 'react-router-dom'
import { api, parseDate } from '../api'
import { useLoad } from '../hooks'
import { useLeague } from '../league'
import { RosterSlots } from '../components/RosterSlots'
import { Empty, ErrorNote, Spinner } from '../components/ui'

export default function RosterPage() {
  const { league, me } = useLeague()
  const teamId = Number(useParams().teamId ?? me.id)
  const { data, error, loading, reload } = useLoad(() => api.roster(league.id, teamId), [league.id, teamId])
  const via = new Map(data?.players.map((e) => [e.player.id, e]) ?? [])

  return (
    <div className="stack">
      <div className="chips scroll-x" role="tablist" aria-label="Teams">
        {league.teams.map((t) => (
          <Link key={t.id} to={`/leagues/${league.id}/roster/${t.id}`} replace className="chip-btn" aria-selected={t.id === teamId}>
            {t.id === me.id ? `${t.name} (you)` : t.name}
          </Link>
        ))}
      </div>
      <ErrorNote error={error} onRetry={() => reload()} />
      {loading && !data ? <Spinner /> : data && (
        <>
          <div className="roster-head">
            <span className="avatar avatar-lg">{data.team.name.slice(0, 1).toUpperCase()}</span>
            <div>
              <h2>{data.team.name}</h2>
              <div className="muted small">{data.players.length} of {Object.values(league.roster_slots).reduce((a, b) => a + b, 0)} players</div>
            </div>
          </div>
          {data.players.length === 0 && league.status === 'setup'
            ? <Empty title="No players yet">Rosters fill up during the draft.</Empty>
            : <RosterSlots players={data.players.map((e) => e.player)} slots={league.roster_slots} sub={(p) => {
                const e = via.get(p.id)
                if (e?.acquired_via !== 'trade') return undefined
                const d = parseDate(e.acquired_at)
                return `via trade${d ? ` ${d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}` : ''}`
              }} />}
          {teamId !== me.id && league.status === 'active' && (
            <Link to={`/leagues/${league.id}/trades?with=${teamId}`} className="btn btn-secondary btn-block">Propose a trade</Link>
          )}
        </>
      )}
    </div>
  )
}
