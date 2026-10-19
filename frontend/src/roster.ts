import { SLOTS, type Player } from './api'
import {  } from './components/ui'
import { normRole } from './format'

export interface SlotRow { slot: string; player: Player | null }

/** Lay players into the league's slots the way the backend counts them:
 * each player fills a slot for their position first, overflow goes to bench. */
export function layoutRoster(players: Player[], slots: Record<string, number>): SlotRow[] {
  const byPos = new Map<string, Player[]>()
  const bench: Player[] = []
  for (const p of players) {
    const pos = normRole(p.role)
    if (!pos || pos === 'bench') { bench.push(p); continue }
    const list = byPos.get(pos) ?? []
    list.push(p)
    byPos.set(pos, list)
  }
  const rows: SlotRow[] = []
  for (const s of SLOTS) {
    if (s === 'bench') continue
    const list = byPos.get(s) ?? []
    for (let i = 0; i < (slots[s] ?? 0); i++) rows.push({ slot: s, player: list[i] ?? null })
    bench.push(...list.slice(slots[s] ?? 0))
  }
  // Players whose position isn't a slot in this league also land on the bench.
  for (const [pos, list] of byPos) if (!SLOTS.includes(pos as never)) bench.push(...list)
  const benchSlots = Math.max(slots.bench ?? 0, bench.length)
  for (let i = 0; i < benchSlots; i++) rows.push({ slot: 'bench', player: bench[i] ?? null })
  return rows
}

/** Mirror of app/services/roster.py roster_fits. */
export function rosterFits(players: Player[], slots: Record<string, number>): boolean {
  const counts = new Map<string | null, number>()
  for (const p of players) {
    const pos = normRole(p.role)
    counts.set(pos, (counts.get(pos) ?? 0) + 1)
  }
  let overflow = 0
  for (const [pos, n] of counts) {
    const cap = pos && pos !== 'bench' ? slots[pos] ?? 0 : 0
    overflow += Math.max(0, n - cap)
  }
  return overflow <= (slots.bench ?? 0)
}
