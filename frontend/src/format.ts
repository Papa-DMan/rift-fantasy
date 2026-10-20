export function normRole(role: string | null | undefined): string | null {
  if (!role) return null
  const r = role.toLowerCase()
  return ({ bottom: 'adc', bot: 'adc', jng: 'jungle', sup: 'support', utility: 'support', middle: 'mid' } as Record<string, string>)[r] ?? r
}

export function formatDateTime(d: Date | null) {
  if (!d) return ''
  return d.toLocaleString(undefined, { weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })
}

export function formatCountdown(ms: number) {
  if (ms <= 0) return '0:00'
  const s = Math.ceil(ms / 1000)
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60
  return h ? `${h}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}` : `${m}:${String(sec).padStart(2, '0')}`
}

/** Labels for scoring rule keys (app/services/scoring.py), in display order. */
export const SCORING_LABELS: Record<string, string> = {
  kills: 'Kill', deaths: 'Death', assists: 'Assist', cs: 'CS', vision_score: 'Vision score',
  first_blood: 'First blood', win: 'Game win', ten_kill_assists: '10+ kills & assists',
  coach_win: 'Coach: game win', damage: 'Damage', gold: 'Gold', cs_at_15: 'CS at 15',
  gold_at_15: 'Gold at 15', objective_steal: 'Objective steal',
}

export function formatPoints(n: number) {
  return String(Math.round(n * 100) / 100)
}

export function ordinal(n: number) {
  const s = ['th', 'st', 'nd', 'rd'], v = n % 100
  return n + (s[(v - 20) % 10] || s[v] || s[0])
}
