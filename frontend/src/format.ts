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
