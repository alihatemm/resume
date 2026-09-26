import { useCallback, useEffect, useState } from 'react'

type AsyncState<T> =
  | { status: 'loading' }
  | { status: 'success'; data: T }
  | { status: 'error'; error: Error }

// Runs `load` whenever `key` changes (or reload() is called) and tracks loading/error.
export function useAsync<T>(load: () => Promise<T>, key: unknown) {
  const [state, setState] = useState<AsyncState<T>>({ status: 'loading' })
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let cancelled = false
    setState({ status: 'loading' })
    load().then(
      (data) => !cancelled && setState({ status: 'success', data }),
      (e: unknown) =>
        !cancelled && setState({ status: 'error', error: e instanceof Error ? e : new Error(String(e)) }),
    )
    return () => {
      cancelled = true
    }
    // `load` is usually an inline closure; `key` is what actually identifies the request.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, attempt])

  const reload = useCallback(() => setAttempt((n) => n + 1), [])
  return { ...state, reload }
}
