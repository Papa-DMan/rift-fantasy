import { useCallback, useEffect, useRef, useState } from 'react'

/** Load data with an async function; re-runs when deps change. */
export function useLoad<T>(fn: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const fnRef = useRef(fn)
  fnRef.current = fn

  const reload = useCallback(async (quiet = false) => {
    if (!quiet) setLoading(true)
    try {
      const d = await fnRef.current()
      setData(d)
      setError(null)
      return d
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }, [])

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { reload() }, deps)
  return { data, setData, error, loading, reload }
}

export function useInterval(fn: () => void, ms: number | null) {
  const ref = useRef(fn)
  ref.current = fn
  useEffect(() => {
    if (ms === null) return
    const id = setInterval(() => ref.current(), ms)
    return () => clearInterval(id)
  }, [ms])
}

/** Re-render every `ms` and return the current time. */
export function useNow(ms = 1000) {
  const [now, setNow] = useState(() => Date.now())
  useInterval(() => setNow(Date.now()), ms)
  return now
}

/** Pause polling while the tab or installed app is in the background. */
export function useVisible() {
  const [visible, setVisible] = useState(() => document.visibilityState === 'visible')
  useEffect(() => {
    const on = () => setVisible(document.visibilityState === 'visible')
    document.addEventListener('visibilitychange', on)
    return () => document.removeEventListener('visibilitychange', on)
  }, [])
  return visible
}
