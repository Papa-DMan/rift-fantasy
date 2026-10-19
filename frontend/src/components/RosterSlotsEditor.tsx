import { SLOTS } from '../api'
import { Stepper } from './ui'

const LABEL: Record<string, string> = {
  top: 'Top', jungle: 'Jungle', mid: 'Mid', adc: 'ADC', support: 'Support', coach: 'Coach', bench: 'Bench',
}

export function RosterSlotsEditor({ value, onChange }: { value: Record<string, number>; onChange: (v: Record<string, number>) => void }) {
  const total = SLOTS.reduce((n, s) => n + (value[s] ?? 0), 0)
  return (
    <div className="slots-editor">
      {SLOTS.map((s) => (
        <div className="slots-row" key={s}>
          <span>{LABEL[s]}</span>
          <Stepper label={LABEL[s]} value={value[s] ?? 0} min={0} max={5}
            onChange={(n) => onChange({ ...value, [s]: n })} />
        </div>
      ))}
      <div className="muted small">{total} players per team, so the draft runs {total} rounds.</div>
    </div>
  )
}
