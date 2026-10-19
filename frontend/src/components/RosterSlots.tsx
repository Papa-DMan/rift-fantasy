import type { Player } from '../api'
import { layoutRoster } from '../roster'
import { RoleBadge } from './ui'

export function RosterSlots({ players, slots, sub }: { players: Player[]; slots: Record<string, number>; sub?: (p: Player) => string | undefined }) {
  const rows = layoutRoster(players, slots)
  return (
    <ul className="card list-plain slots">
      {rows.map((r, i) => (
        <li key={i} className={r.player ? '' : 'slot-empty'}>
          <span className="slot-label">{r.slot === 'bench' ? 'BN' : <RoleBadge role={r.slot} />}</span>
          {r.player ? (
            <span className="grow">
              <span className="player-name">{r.player.name}</span>
              <span className="player-sub">
                {r.player.team_code ?? 'Free agent'}
                {r.slot === 'bench' && r.player.role && <> · {r.player.role}</>}
                {sub?.(r.player) && <> · {sub(r.player)}</>}
              </span>
            </span>
          ) : <span className="grow muted">Empty</span>}
        </li>
      ))}
    </ul>
  )
}
