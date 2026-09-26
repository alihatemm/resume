import { useState } from 'react'
import { api } from '../api'
import { relativeTime } from '../format'
import type { SinceYouLeft as Since } from '../types'
import { useAsync } from '../useAsync'

// "Since you left": what happened in the repo after this checkpoint. Loaded on its own so it can
// never block or break the saved checkpoint; any failure simply hides the section.
export function SinceYouLeft({ id }: { id: number }) {
  const result = useAsync(() => api.sinceCheckpoint(id), id)

  if (result.status === 'loading') {
    return <div className="h-10 animate-pulse rounded-lg border border-zinc-800/60 bg-zinc-900/30" aria-hidden />
  }
  if (result.status === 'error') return null
  const s = result.data
  if (s.status === 'unavailable' && s.reason === 'git_error') return null
  return <SinceStrip since={s} />
}

function plural(n: number, word: string) {
  return `${n} ${word}${n === 1 ? '' : 's'}`
}

function SinceStrip({ since: s }: { since: Since }) {
  const [open, setOpen] = useState(false)
  const rewritten = s.status === 'changed' && s.history !== 'linear'
  const branchMoved = s.current_branch !== null && s.current_branch !== s.saved_branch
  const expandable =
    s.status === 'changed' ? s.commits.length > 0 || s.files.length > 0 : s.uncommitted_paths.length > 0

  let headline
  if (s.status === 'changed' && !rewritten && !branchMoved) {
    headline = (
      <>
        <span className="font-medium text-zinc-200">
          {plural(s.commits_ahead, 'commit')} · {plural(s.files_changed, 'file')}
        </span>{' '}
        changed since you saved this
      </>
    )
  } else if (s.status === 'unchanged') {
    headline = (
      <>
        Nothing has changed since this checkpoint
        {s.uncommitted_files > 0 && (
          <span className="text-zinc-500"> · {plural(s.uncommitted_files, 'file')} with uncommitted changes</span>
        )}
      </>
    )
  } else {
    headline = s.message // history rewritten, branch switched, or unavailable: server wording is explicit
  }

  return (
    <section
      aria-label="Since you left"
      className={`rounded-lg border px-4 py-2.5 text-sm ${
        rewritten ? 'border-amber-500/20 bg-amber-500/5 text-amber-200/90' : 'border-zinc-800/70 bg-zinc-900/30 text-zinc-400'
      }`}
    >
      <div className="flex items-start gap-3">
        <span className="mt-px shrink-0 text-[11px] font-semibold tracking-wider text-zinc-500 uppercase">
          Since you left
        </span>
        <p className="min-w-0 flex-1">{headline}</p>
        {expandable && (
          <button
            type="button"
            onClick={() => setOpen((o) => !o)}
            aria-expanded={open}
            className="shrink-0 text-xs text-zinc-500 transition-colors hover:text-zinc-200"
          >
            {open ? 'Hide' : 'Show'}
          </button>
        )}
      </div>

      {open && (
        <div className="mt-3 space-y-3 border-t border-zinc-800/70 pt-3 font-mono text-xs">
          {s.commits.length > 0 && (
            <ul className="space-y-1">
              {s.commits.map((c) => (
                <li key={c.sha} className="flex gap-2 text-zinc-400">
                  <span className="shrink-0 text-zinc-600">{c.sha}</span>
                  <span className="min-w-0 flex-1 truncate text-zinc-300" title={c.subject}>
                    {c.subject}
                  </span>
                  <span className="shrink-0 text-zinc-600">
                    {c.author} · {relativeTime(c.date)}
                  </span>
                </li>
              ))}
              {s.commits_truncated && (
                <li className="text-zinc-600">+ {s.commits_ahead - s.commits.length} more commits</li>
              )}
            </ul>
          )}
          {s.files.length > 0 && (
            <ul className="space-y-0.5">
              {s.files.map((f) => (
                <li key={f.path} className="flex gap-2 text-zinc-400">
                  <span className="w-3 shrink-0 text-zinc-600">{f.status}</span>
                  <span className="truncate" title={f.path}>
                    {f.path}
                  </span>
                </li>
              ))}
              {s.files_truncated && <li className="text-zinc-600">+ {s.files_changed - s.files.length} more files</li>}
            </ul>
          )}
          {s.uncommitted_paths.length > 0 && (
            <div>
              <p className="mb-1 text-zinc-600">Uncommitted now</p>
              <ul className="space-y-0.5 text-zinc-400">
                {s.uncommitted_paths.map((p) => (
                  <li key={p} className="truncate" title={p}>
                    {p}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </section>
  )
}
