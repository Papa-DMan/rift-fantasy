import { useEffect, type ReactNode } from 'react'
import type { Player } from '../api'
import { normRole } from '../format'

export function Spinner({ label }: { label?: string }) {
  return <div className="spinner-wrap" role="status"><span className="spinner" />{label && <span>{label}</span>}</div>
}

export function ErrorNote({ error, onRetry }: { error: string | null; onRetry?: () => void }) {
  if (!error) return null
  return (
    <div className="note note-error" role="alert">
      <span style={{ whiteSpace: 'pre-line' }}>{error}</span>
      {onRetry && <button className="btn btn-ghost btn-sm" onClick={onRetry}>Retry</button>}
    </div>
  )
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return <div className="empty"><strong>{title}</strong>{children && <div className="muted">{children}</div>}</div>
}

const ROLE_LABEL: Record<string, string> = {
  top: 'TOP', jungle: 'JGL', mid: 'MID', adc: 'ADC', support: 'SUP', coach: 'COACH', bench: 'BENCH',
}

export function RoleBadge({ role }: { role: string | null | undefined }) {
  const r = normRole(role)
  return <span className={`role role-${r ?? 'none'}`}>{r ? ROLE_LABEL[r] ?? r.toUpperCase() : '—'}</span>
}

export function PlayerLine({ player, right, sub }: { player: Player | undefined; right?: ReactNode; sub?: ReactNode }) {
  return (
    <div className="player-line">
      <RoleBadge role={player?.role} />
      <div className="player-main">
        <div className="player-name">{player?.name ?? 'Unknown player'}</div>
        <div className="player-sub">{player?.team_code ?? 'Free agent'}{sub && <> · {sub}</>}</div>
      </div>
      {right}
    </div>
  )
}

export function StatusChip({ status }: { status: string }) {
  const label = status.replace('_', ' ')
  return <span className={`chip chip-${status}`}>{label}</span>
}

export function Sheet({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: string; children: ReactNode }) {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    return () => { document.removeEventListener('keydown', onKey); document.body.style.overflow = '' }
  }, [open, onClose])
  if (!open) return null
  return (
    <div className="sheet-backdrop" onClick={onClose}>
      <div className="sheet" role="dialog" aria-modal="true" aria-label={title} onClick={(e) => e.stopPropagation()}>
        <div className="sheet-handle" />
        <div className="sheet-head">
          <h2>{title}</h2>
          <button className="icon-btn" onClick={onClose} aria-label="Close">✕</button>
        </div>
        <div className="sheet-body">{children}</div>
      </div>
    </div>
  )
}

export function Stepper({ value, min, max, onChange, label }: { value: number; min: number; max: number; onChange: (n: number) => void; label: string }) {
  return (
    <div className="stepper" aria-label={label}>
      <button type="button" className="icon-btn" disabled={value <= min} onClick={() => onChange(value - 1)} aria-label={`Fewer ${label}`}>−</button>
      <span className="stepper-val">{value}</span>
      <button type="button" className="icon-btn" disabled={value >= max} onClick={() => onChange(value + 1)} aria-label={`More ${label}`}>+</button>
    </div>
  )
}

