import type { CheckpointStatus } from '../types'

export function StatusBadge({ status }: { status: CheckpointStatus }) {
  if (status === 'ai_failed') {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full font-sans border border-amber-400/30 bg-amber-400/10 px-2 py-0.5 text-xs font-medium text-amber-300">
        <span className="h-1.5 w-1.5 rounded-full bg-amber-400" aria-hidden />
        AI unavailable
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full font-sans border border-zinc-800 px-2 py-0.5 text-xs font-medium text-zinc-400">
      <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" aria-hidden />
      Ready
    </span>
  )
}
