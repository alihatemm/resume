import { useEffect, useState } from 'react'
import { api } from './api'
import type { Health } from './types'

// M0 placeholder: proves frontend → backend → config wiring. Replaced in M1.
function App() {
  const [health, setHealth] = useState<Health | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.health().then(setHealth).catch((e: Error) => setError(e.message))
  }, [])

  return (
    <main className="mx-auto flex min-h-screen max-w-xl flex-col justify-center gap-6 px-6">
      <div>
        <h1 className="text-4xl font-semibold tracking-tight">Resume</h1>
        <p className="mt-1 text-zinc-400">Pick up exactly where you left off.</p>
      </div>

      <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5 font-mono text-sm">
        {error && <p className="text-red-400">Backend unreachable: {error}</p>}
        {!error && !health && <p className="text-zinc-500">Checking backend…</p>}
        {health && (
          <ul className="space-y-1">
            <li>
              backend: <span className="text-emerald-400">{health.status}</span>
            </li>
            <li>
              gemini key:{' '}
              {health.gemini_configured ? (
                <span className="text-emerald-400">configured</span>
              ) : (
                <span className="text-amber-400">missing</span>
              )}
            </li>
            <li>
              model: <span className="text-zinc-300">{health.model}</span>
            </li>
          </ul>
        )}
      </div>
    </main>
  )
}

export default App
