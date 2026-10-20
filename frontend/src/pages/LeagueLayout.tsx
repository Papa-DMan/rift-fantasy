import { useMemo } from 'react'
import { Link, NavLink, Outlet, useParams } from 'react-router-dom'
import { api } from '../api'
import { useLoad } from '../hooks'
import { ErrorNote, Spinner, StatusChip } from '../components/ui'
import type { LeagueCtx } from '../league'

export default function LeagueLayout() {
  const id = Number(useParams().leagueId)
  const league = useLoad(() => api.league(id), [id])
  // Every player, owned or not, so boards, rosters and trades can show names.
  const players = useLoad(() => api.players(id, { available: false }), [id])

  const ctx = useMemo<LeagueCtx | null>(() => {
    if (!league.data || !players.data) return null
    const me = league.data.teams.find((t) => t.id === league.data!.my_team_id)!
    return {
      league: league.data, me,
      teamsById: new Map(league.data.teams.map((t) => [t.id, t])),
      playersById: new Map(players.data.map((p) => [p.id, p])),
      reloadLeague: () => league.reload(true),
      reloadPlayers: () => players.reload(true),
    }
  }, [league, players])

  const tabs = [
    { to: '', label: 'League', icon: '🏆', end: true },
    { to: 'draft', label: 'Draft', icon: '🎯', live: league.data?.status === 'drafting' },
    { to: 'roster', label: 'Rosters', icon: '🛡️' },
    { to: 'trades', label: 'Trades', icon: '🔁' },
  ]

  return (
    <div className="page has-tabs">
      <header className="topbar">
        <Link to="/" className="icon-btn" aria-label="All leagues">‹</Link>
        <div className="topbar-title">{league.data?.name ?? 'League'}</div>
        {league.data ? <StatusChip status={league.data.status} /> : <span style={{ width: 40 }} />}
      </header>
      <main className="content">
        <ErrorNote error={league.error ?? players.error} onRetry={() => { league.reload(); players.reload() }} />
        {ctx ? <Outlet context={ctx} /> : !league.error && !players.error && <Spinner label="Loading league" />}
      </main>
      <nav className="tabbar" aria-label="League sections">
        {tabs.map((t) => (
          <NavLink key={t.to} to={t.to} end={t.end} className="tab">
            <span className="tab-icon" aria-hidden>{t.icon}</span>
            <span>{t.label}</span>
            {t.live && <span className="live-dot" aria-label="live" />}
          </NavLink>
        ))}
      </nav>
    </div>
  )
}
