import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { useAuth } from './auth'
import { Spinner } from './components/ui'
import AuthPage from './pages/AuthPage'
import Home from './pages/Home'
import CreateLeague from './pages/CreateLeague'
import JoinLeague from './pages/JoinLeague'
import LeagueLayout from './pages/LeagueLayout'
import Overview from './pages/Overview'
import DraftPage from './pages/DraftPage'
import RosterPage from './pages/RosterPage'
import TradesPage from './pages/TradesPage'

export default function App() {
  const { user, loading } = useAuth()
  const location = useLocation()

  if (loading) return <div className="center-screen"><Spinner label="Loading" /></div>
  if (!user) {
    return (
      <Routes>
        <Route path="/login" element={<AuthPage />} />
        <Route path="*" element={<Navigate to="/login" replace state={{ from: location.pathname + location.search }} />} />
      </Routes>
    )
  }
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/login" element={<Navigate to={(location.state as { from?: string } | null)?.from ?? '/'} replace />} />
      <Route path="/new" element={<CreateLeague />} />
      <Route path="/join" element={<JoinLeague />} />
      <Route path="/leagues/:leagueId" element={<LeagueLayout />}>
        <Route index element={<Overview />} />
        <Route path="draft" element={<DraftPage />} />
        <Route path="roster" element={<RosterPage />} />
        <Route path="roster/:teamId" element={<RosterPage />} />
        <Route path="trades" element={<TradesPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
