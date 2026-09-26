import { fullDateTime, relativeTime } from '../format'
import { href, paths } from '../router'
import type { CheckpointListItem } from '../types'
import { StatusBadge } from './StatusBadge'

export function CheckpointCard({ checkpoint: c }: { checkpoint: CheckpointListItem }) {
  // ai_failed may still carry a basic fallback summary (title/next_step); be truthful either way.
  const failed = c.status === 'ai_failed'
  const hasSummary = Boolean(c.title || c.next_step)

  return (
    <a
      href={href(paths.detail(c.id))}
      className="group block rounded-lg border border-zinc-800 bg-zinc-900/50 px-4 py-4 transition-colors hover:border-zinc-600 hover:bg-zinc-900 focus-visible:border-emerald-400/60 focus-visible:outline-none sm:px-5"
    >
      <div className="flex items-center justify-between gap-3 font-mono text-xs text-zinc-400">
        <span className="min-w-0 truncate">
          <span className="text-zinc-200">{c.repo_name}</span>
          <span className="px-1.5 text-zinc-600">/</span>
          {c.branch}
        </span>
        <time dateTime={c.created_at} title={fullDateTime(c.created_at)} className="shrink-0">
          {relativeTime(c.created_at)}
        </time>
      </div>

      <div className="mt-2 flex flex-wrap items-start justify-between gap-x-3 gap-y-1.5">
        <h3 className="min-w-0 text-base leading-snug font-medium text-zinc-50">{c.title || 'Untitled checkpoint'}</h3>
        {failed && (hasSummary ? <BasicSummaryLabel /> : <StatusBadge status={c.status} />)}
      </div>

      <div className="mt-2.5 flex items-start gap-2.5">
        {c.next_step ? (
          <>
            <span className="mt-px shrink-0 rounded bg-emerald-400/10 px-1.5 py-0.5 font-mono text-[10px] leading-4 font-semibold tracking-wider text-emerald-300">
              NEXT
            </span>
            <p className="line-clamp-2 min-w-0 flex-1 text-sm leading-relaxed text-zinc-300">{c.next_step}</p>
          </>
        ) : (
          <p className="min-w-0 flex-1 text-sm text-zinc-400">Open to see your note and git changes.</p>
        )}
        <span
          className="mt-0.5 hidden shrink-0 text-xs font-medium text-zinc-500 transition-colors group-hover:text-emerald-300 sm:inline"
          aria-hidden
        >
          Resume →
        </span>
      </div>
    </a>
  )
}

// Muted rather than alarming: the checkpoint is usable, but this isn't a full AI summary.
function BasicSummaryLabel() {
  return (
    <span className="inline-flex shrink-0 items-center gap-1.5 rounded-full border border-amber-400/25 px-2 py-0.5 text-xs font-medium text-amber-300/90">
      <span className="h-1.5 w-1.5 rounded-full bg-amber-400/80" aria-hidden />
      Basic recovery summary
    </span>
  )
}
