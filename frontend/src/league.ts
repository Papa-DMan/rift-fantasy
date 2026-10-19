import { useOutletContext } from 'react-router-dom'
import type { LeagueDetail, Player, Team } from './api'

export interface LeagueCtx {
  league: LeagueDetail
  me: Team
  teamsById: Map<number, Team>
  playersById: Map<number, Player>
  reloadLeague: () => Promise<unknown>
  reloadPlayers: () => Promise<unknown>
}

export const useLeague = () => useOutletContext<LeagueCtx>()
