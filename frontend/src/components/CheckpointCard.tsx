import { fullDateTime, relativeTime } from '../format'
import { href, paths } from '../router'
import type { CheckpointListItem } from '../types'
import { StatusBadge } from './StatusBadge'

export function CheckpointCard({ checkpoint: c }: { checkpoint: CheckpointListItem }) {
  const failed = c.status === 'ai_failed'

  return (
    <a
      href={href(paths.detail(c.id))}
      className="group block rounded-lg border border-zinc-800/80 bg-zinc-900/40 px-4 py-3.5 transition-colors hover:border-zinc-700 hover:bg-zinc-900 focus-visible:border-emerald-400/60 focus-visible:outline-none"
    >
      <div className="flex items-center justify-between gap-3 font-mono text-xs text-zinc-500">
        <span className="min-w-0 truncate">
          <span className="text-zinc-300">{c.repo_name}</span>
          <span className="px-1.5 text-zinc-700">/</span>
          {c.branch}
        </span>
        <time dateTime={c.created_at} title={fullDateTime(c.created_at)} className="shrink-0">
          {relativeTime(c.created_at)}
        </time>
      </div>

      <div className="mt-2 flex items-start justify-between gap-3">
        <h3 className="min-w-0 text-[15px] leading-snug font-medium text-zinc-100">
          {c.title || 'Untitled checkpoint'}
        </h3>
        {failed && <StatusBadge status={c.status} />}
      </div>

      <p className="mt-1.5 flex gap-2 text-sm text-zinc-400">
        <span className="shrink-0 text-emerald-400/80" aria-hidden>
          →
        </span>
        <span className="min-w-0 truncate">
          {c.next_step || <span className="text-zinc-500">Open to see your note and git changes.</span>}
        </span>
      </p>
    </a>
  )
}
