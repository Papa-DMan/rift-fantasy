import { Link } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import { useLoad } from '../hooks'
import { Empty, ErrorNote, Spinner, StatusChip } from '../components/ui'
import { InstallPrompt } from '../components/InstallPrompt'

export default function Home() {
  const { user, logout } = useAuth()
  const { data: leagues, error, loading, reload } = useLoad(() => api.leagues(), [])

  return (
    <div className="page">
      <header className="topbar">
        <div className="brand"><img src="/icons/icon-192.png" alt="" width={28} height={28} /> Rift Fantasy</div>
        <button className="btn btn-ghost btn-sm" onClick={logout}>Sign out</button>
      </header>
      <main className="content">
        <h1 className="greeting">Hey {user?.display_name} 👋</h1>
        <InstallPrompt />
        <div className="action-row">
          <Link to="/new" className="btn btn-primary">Create league</Link>
          <Link to="/join" className="btn btn-secondary">Join with code</Link>
        </div>
        <h2 className="section-title">Your leagues</h2>
        <ErrorNote error={error} onRetry={() => reload()} />
        {loading && !leagues ? <Spinner /> : leagues && leagues.length === 0 ? (
          <Empty title="No leagues yet">Create one and send the invite code to your friends, or join theirs.</Empty>
        ) : (
          <ul className="list">
            {leagues?.map((l) => (
              <li key={l.id}>
                <Link to={`/leagues/${l.id}`} className="card league-card">
                  <div>
                    <div className="league-name">{l.name}</div>
                    <div className="muted small">{l.tournament_id} · up to {l.max_teams} teams</div>
                  </div>
                  <StatusChip status={l.status} />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </main>
    </div>
  )
}
