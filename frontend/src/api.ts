// Thin client for the LoL Fantasy FastAPI backend. Types mirror app/schemas.py.

const BASE = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') ?? '/api'
const TOKEN_KEY = 'rf.token'

export type LeagueStatus = 'setup' | 'drafting' | 'active' | 'finished'
export type DraftType = 'snake' | 'linear'
export type DraftStatus = 'scheduled' | 'in_progress' | 'complete'
export type TradeStatus = 'proposed' | 'accepted' | 'rejected' | 'cancelled' | 'vetoed' | 'completed'
export type Slot = 'top' | 'jungle' | 'mid' | 'adc' | 'support' | 'coach' | 'bench'

export const SLOTS: Slot[] = ['top', 'jungle', 'mid', 'adc', 'support', 'coach', 'bench']
export const POSITIONS: Exclude<Slot, 'bench'>[] = ['top', 'jungle', 'mid', 'adc', 'support', 'coach']

export interface User { id: number; email: string; display_name: string; created_at?: string | null }
export interface Team { id: number; name: string; user_id: number; is_commissioner: boolean; joined_at?: string | null }
export interface League {
  id: number; name: string; tournament_id: string; max_teams: number; status: LeagueStatus
  roster_slots: Record<string, number>; trade_deadline: string | null; created_by_id: number; created_at?: string | null
}
export interface LeagueDetail extends League { teams: Team[]; invite_code: string | null; my_team_id: number }
export interface Player { id: number; name: string; role: string | null; team_code: string | null }
export interface RosterEntry { player: Player; acquired_via: string; acquired_at: string | null }
export interface Roster { team: Team; players: RosterEntry[] }
export interface DraftPick {
  overall_pick: number; round_number: number; team_id: number; player_id: number | null
  is_autopick: boolean; picked_at: string | null
}
export interface Draft {
  id: number; type: DraftType; status: DraftStatus; scheduled_for: string | null; seconds_per_pick: number
  started_at: string | null; completed_at: string | null; total_rounds: number
  on_the_clock_team_id: number | null; current_pick: number | null; pick_deadline: string | null; picks: DraftPick[]
}
export interface TradeItem { from_team_id: number; player_id: number }
export interface Trade {
  id: number; league_id: number; proposer_team_id: number; receiver_team_id: number; status: TradeStatus
  message: string | null; created_at?: string | null; responded_at: string | null; completed_at: string | null
  items: TradeItem[]
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) { super(message); this.status = status }
}

export const tokenStore = {
  get: () => { try { return localStorage.getItem(TOKEN_KEY) } catch { return null } },
  set: (t: string | null) => {
    try { if (t) localStorage.setItem(TOKEN_KEY, t); else localStorage.removeItem(TOKEN_KEY) } catch { /* private mode */ }
  },
}

let onUnauthorized: (() => void) | null = null
export function setUnauthorizedHandler(fn: (() => void) | null) { onUnauthorized = fn }

function errorMessage(body: unknown, status: number): string {
  const detail = (body as { detail?: unknown } | null)?.detail
  if (typeof detail === 'string') return detail
  // FastAPI validation errors: [{loc, msg}, ...]
  if (Array.isArray(detail) && detail.length) {
    return detail.map((d: { loc?: unknown[]; msg?: string }) => {
      const field = d.loc?.filter((x) => x !== 'body').join('.')
      return field ? `${field}: ${d.msg}` : d.msg
    }).join('\n')
  }
  if (status === 0) return "Can't reach the server. Check your connection."
  return `Something went wrong (${status})`
}

async function request<T>(method: string, path: string, body?: unknown, form?: URLSearchParams): Promise<T> {
  const headers: Record<string, string> = {}
  const token = tokenStore.get()
  if (token) headers.Authorization = `Bearer ${token}`
  let payload: BodyInit | undefined
  if (form) { payload = form; headers['Content-Type'] = 'application/x-www-form-urlencoded' }
  else if (body !== undefined) { payload = JSON.stringify(body); headers['Content-Type'] = 'application/json' }

  let res: Response
  try {
    res = await fetch(`${BASE}${path}`, { method, headers, body: payload })
  } catch {
    throw new ApiError(0, errorMessage(null, 0))
  }
  if (res.status === 204) return undefined as T
  const data = await res.json().catch(() => null)
  if (!res.ok) {
    if (res.status === 401 && token && path !== '/auth/login') onUnauthorized?.()
    throw new ApiError(res.status, errorMessage(data, res.status))
  }
  return data as T
}

const get = <T>(p: string) => request<T>('GET', p)
const post = <T>(p: string, b?: unknown) => request<T>('POST', p, b)
const patch = <T>(p: string, b?: unknown) => request<T>('PATCH', p, b)

export const api = {
  register: (b: { email: string; password: string; display_name: string }) => post<User>('/auth/register', b),
  login: (email: string, password: string) =>
    request<{ access_token: string }>('POST', '/auth/login', undefined, new URLSearchParams({ username: email, password })),
  me: () => get<User>('/users/me'),

  leagues: () => get<League[]>('/leagues'),
  league: (id: number) => get<LeagueDetail>(`/leagues/${id}`),
  createLeague: (b: { name: string; team_name: string; max_teams?: number; roster_slots?: Record<string, number>; trade_deadline?: string | null }) =>
    post<LeagueDetail>('/leagues', b),
  updateLeague: (id: number, b: Partial<Pick<League, 'name' | 'max_teams' | 'roster_slots' | 'trade_deadline'>>) =>
    patch<LeagueDetail>(`/leagues/${id}`, b),
  joinLeague: (invite_code: string, team_name: string) => post<LeagueDetail>('/leagues/join', { invite_code, team_name }),
  rotateInvite: (id: number) => post<LeagueDetail>(`/leagues/${id}/invite-code`),
  leaveLeague: (id: number) => post<void>(`/leagues/${id}/leave`),
  roster: (leagueId: number, teamId: number) => get<Roster>(`/leagues/${leagueId}/teams/${teamId}/roster`),
  players: (leagueId: number, opts: { available?: boolean; position?: string } = {}) => {
    const q = new URLSearchParams({ available: String(opts.available ?? true) })
    if (opts.position) q.set('position', opts.position)
    return get<Player[]>(`/leagues/${leagueId}/players?${q}`)
  },

  draft: (leagueId: number) => get<Draft>(`/leagues/${leagueId}/draft`),
  updateDraft: (leagueId: number, b: { type?: DraftType; seconds_per_pick?: number; scheduled_for?: string | null }) =>
    patch<Draft>(`/leagues/${leagueId}/draft`, b),
  startDraft: (leagueId: number, order?: number[]) => post<Draft>(`/leagues/${leagueId}/draft/start`, order ? { order } : undefined),
  pick: (leagueId: number, player_id: number) => post<Draft>(`/leagues/${leagueId}/draft/pick`, { player_id }),

  trades: (leagueId: number, opts: { status?: TradeStatus; mine?: boolean } = {}) => {
    const q = new URLSearchParams()
    if (opts.status) q.set('status_filter', opts.status)
    if (opts.mine) q.set('mine', 'true')
    return get<Trade[]>(`/leagues/${leagueId}/trades${q.size ? `?${q}` : ''}`)
  },
  proposeTrade: (leagueId: number, b: { receiver_team_id: number; give_player_ids: number[]; receive_player_ids: number[]; message?: string }) =>
    post<Trade>(`/leagues/${leagueId}/trades`, b),
  tradeAction: (leagueId: number, tradeId: number, action: 'accept' | 'reject' | 'cancel') =>
    post<Trade>(`/leagues/${leagueId}/trades/${tradeId}/${action}`),
}

/** The backend may return naive datetimes (SQLite); they are UTC. */
export function parseDate(s: string | null | undefined): Date | null {
  if (!s) return null
  return new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(s) ? s : `${s}Z`)
}

/** Value for <input type="datetime-local"> from an API datetime, in local time. */
export function toLocalInput(s: string | null | undefined): string {
  const d = parseDate(s)
  if (!d) return ''
  const off = d.getTimezoneOffset() * 60000
  return new Date(d.getTime() - off).toISOString().slice(0, 16)
}

export function fromLocalInput(v: string): string | null {
  return v ? new Date(v).toISOString() : null
}
