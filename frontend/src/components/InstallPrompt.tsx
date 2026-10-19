import { useEffect, useState } from 'react'

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
}

const DISMISS_KEY = 'rf.installDismissed'

function isStandalone() {
  return window.matchMedia('(display-mode: standalone)').matches ||
    (navigator as Navigator & { standalone?: boolean }).standalone === true
}

function isIos() {
  return /iphone|ipad|ipod/i.test(navigator.userAgent) ||
    (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)
}

/** "Add to Home Screen" nudge: a real install button on Android/desktop
 * Chrome, and share-sheet instructions on iOS Safari (which has no API). */
export function InstallPrompt() {
  const [deferred, setDeferred] = useState<BeforeInstallPromptEvent | null>(null)
  const [dismissed, setDismissed] = useState(() => {
    try { return localStorage.getItem(DISMISS_KEY) === '1' } catch { return false }
  })
  const [installed, setInstalled] = useState(isStandalone)

  useEffect(() => {
    const onPrompt = (e: Event) => { e.preventDefault(); setDeferred(e as BeforeInstallPromptEvent) }
    const onInstalled = () => setInstalled(true)
    window.addEventListener('beforeinstallprompt', onPrompt)
    window.addEventListener('appinstalled', onInstalled)
    return () => {
      window.removeEventListener('beforeinstallprompt', onPrompt)
      window.removeEventListener('appinstalled', onInstalled)
    }
  }, [])

  const dismiss = () => {
    setDismissed(true)
    try { localStorage.setItem(DISMISS_KEY, '1') } catch { /* ignore */ }
  }

  if (installed || dismissed) return null
  if (!deferred && !isIos()) return null

  return (
    <div className="install card">
      <img src="/icons/icon-192.png" alt="" width={44} height={44} />
      <div className="install-text">
        <strong>Get the app</strong>
        {deferred
          ? <span className="muted">Install Rift Fantasy on your home screen.</span>
          : <span className="muted">Tap <ShareIcon /> Share, then <b>Add to Home Screen</b>.</span>}
      </div>
      {deferred && (
        <button className="btn btn-primary btn-sm" onClick={async () => {
          await deferred.prompt()
          const { outcome } = await deferred.userChoice
          if (outcome === 'accepted') setInstalled(true)
          setDeferred(null)
        }}>Install</button>
      )}
      <button className="icon-btn" aria-label="Dismiss" onClick={dismiss}>✕</button>
    </div>
  )
}

function ShareIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" aria-label="Share" style={{ verticalAlign: '-2px' }}>
      <path d="M12 3v12M7 8l5-5 5 5M5 12v8h14v-8" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
