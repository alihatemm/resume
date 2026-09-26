import { checkpoints, NotFoundError } from '../checkpoints'
import { LinkButton } from '../components/Button'
import { FileRow } from '../components/FileRow'
import { NextStepCard } from '../components/NextStepCard'
import { Section } from '../components/Section'
import { ErrorState, LoadingState } from '../components/States'
import { SinceYouLeft } from '../components/SinceYouLeft'
import { StatusBadge } from '../components/StatusBadge'
import { fullDateTime, linkLabel, relativeTime, shortSha, vscodeFileUri } from '../format'
import { href, paths } from '../router'
import type { Checkpoint, FileRef, GitContext, Summary } from '../types'
import { useAsync } from '../useAsync'

export function CheckpointDetail({ id }: { id: number }) {
  const result = useAsync(() => checkpoints.get(id), id)

  return (
    <div>
      <a
        href={href(paths.dashboard)}
        className="mb-6 inline-block text-sm text-zinc-500 transition-colors hover:text-zinc-200"
      >
        ← All checkpoints
      </a>

      {result.status === 'loading' && <LoadingState variant="detail" />}

      {result.status === 'error' &&
        (result.error instanceof NotFoundError ? (
          <ErrorState
            title="Checkpoint not found"
            message={result.error.message}
            action={
              <LinkButton variant="ghost" href={href(paths.dashboard)}>
                Back to checkpoints
              </LinkButton>
            }
          />
        ) : (
          <ErrorState title="Couldn't load this checkpoint" message={result.error.message} onRetry={result.reload} />
        ))}

      {result.status === 'success' && <Restore checkpoint={result.data} />}
    </div>
  )
}

// status 'ai_failed' only means Gemini didn't run. The backend may still attach a basic
// fallback summary (render it normally, with a small warning) or none at all (raw context).
function Restore({ checkpoint: c }: { checkpoint: Checkpoint }) {
  const aiFailed = c.status === 'ai_failed'
  const title = c.summary?.title || c.note.split('\n')[0].slice(0, 80) || 'Untitled checkpoint'
  const resumeTarget = c.summary ? findResumeTarget(c.summary.files) : null

  return (
    <article>
      <header>
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 font-mono text-xs text-zinc-500">
          <span className="text-zinc-300">{c.git.repo_name}</span>
          <span className="text-zinc-700">/</span>
          <span>{c.git.branch}</span>
          <span className="text-zinc-700">·</span>
          <span>{shortSha(c.git.head_sha)}</span>
          <span className="text-zinc-700">·</span>
          <time dateTime={c.created_at} title={fullDateTime(c.created_at)}>
            {relativeTime(c.created_at)}
          </time>
          <span className="ml-1">
            <StatusBadge status={c.status} />
          </span>
        </div>
        <h1 className="mt-3 text-2xl font-semibold tracking-tight text-balance sm:text-3xl">
          {title}
        </h1>
      </header>

      <div className="mt-8 space-y-10">
        <div className="space-y-3">
          {c.summary ? (
            <>
              {aiFailed && <FallbackWarning />}
              <NextStepCard
                step={c.summary.next_step}
                detail={c.summary.next_step_detail}
                action={resumeTarget && <ResumeWorkAction target={resumeTarget} />}
              />
            </>
          ) : (
            <NoSummaryNotice />
          )}
          {/* Loads separately; never blocks the saved checkpoint above. */}
          <SinceYouLeft id={c.id} />
        </div>

        {c.summary && <SummaryView summary={c.summary} />}

        {c.note && (
          <Section title="Your note">
            <p className="rounded-lg border border-zinc-800 bg-zinc-900/40 px-4 py-3 text-[15px] whitespace-pre-wrap text-zinc-300">
              {c.note}
            </p>
          </Section>
        )}

        {c.terminal_text && aiFailed && (
          <Section title="Terminal output">
            <Code>{c.terminal_text}</Code>
          </Section>
        )}

        <GitDetails git={c.git} defaultOpen={!c.summary} />
      </div>
    </article>
  )
}

// One-click jump to the most relevant file: the first one (files are most-important-first)
// with a usable backend-verified abs_path. Null when nothing can be opened, so the card shows
// no action at all rather than a dead or disabled button.
function findResumeTarget(files: FileRef[]): (FileRef & { abs_path: string }) | null {
  const target = files.find((f) => f.abs_path !== null && f.abs_path.trim() !== '')
  return target?.abs_path ? { ...target, abs_path: target.abs_path } : null
}

// Opens the target's line when known, else just the file (vscodeFileUri handles both).
function ResumeWorkAction({ target }: { target: FileRef & { abs_path: string } }) {
  const location = `${target.path}${target.line !== null ? `:${target.line}` : ''}`

  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
      <LinkButton href={vscodeFileUri(target.abs_path, target.line)} title={`Open in VS Code: ${location}`}>
        Resume work ↗
      </LinkButton>
      <span className="min-w-0 truncate font-mono text-xs text-zinc-400" title={location}>
        {location}
      </span>
    </div>
  )
}

function SummaryView({ summary: s }: { summary: Summary }) {
  return (
    <>
      {s.files.length > 0 && (
        <Section title="Open these files">
          <ul className="space-y-2">
            {s.files.map((f) => (
              <FileRow key={f.path} file={f} />
            ))}
          </ul>
        </Section>
      )}

      <div className="grid gap-8 sm:grid-cols-2">
        {s.doing && (
          <Section title="What you were doing">
            <p className="text-[15px] leading-relaxed text-zinc-300">{s.doing}</p>
          </Section>
        )}
        {s.problem && (
          <Section title="Where you got stuck">
            <p className="text-[15px] leading-relaxed text-zinc-300">{s.problem}</p>
          </Section>
        )}
      </div>

      {s.tried.length > 0 && (
        <Section title="Already tried">
          <ul className="space-y-1.5">
            {s.tried.map((t) => (
              <li key={t} className="flex gap-2.5 text-[15px] text-zinc-400">
                <span className="text-zinc-600" aria-hidden>
                  ✕
                </span>
                {t}
              </li>
            ))}
          </ul>
        </Section>
      )}

      {s.errors.length > 0 && (
        <Section title="Errors">
          <div className="space-y-2">
            {s.errors.map((e) => (
              <Code key={e} tone="error">
                {e}
              </Code>
            ))}
          </div>
        </Section>
      )}

      {s.links.length > 0 && (
        <Section title="Links">
          <ul className="space-y-1.5">
            {s.links.map((l) => (
              <li key={l.url}>
                <a
                  href={l.url}
                  target="_blank"
                  rel="noreferrer"
                  className="group inline-flex flex-wrap items-baseline gap-x-2 text-[15px] text-zinc-200 hover:text-white"
                >
                  <span className="underline decoration-zinc-700 underline-offset-4 group-hover:decoration-emerald-400">
                    {l.title}
                  </span>
                  <span className="font-mono text-xs text-zinc-500">{linkLabel(l.url)} ↗</span>
                </a>
              </li>
            ))}
          </ul>
        </Section>
      )}
    </>
  )
}

function FallbackWarning() {
  return (
    <p className="flex items-center gap-2 text-sm text-amber-300/90">
      <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-amber-400" aria-hidden />
      AI summary unavailable — showing basic recovery summary
    </p>
  )
}

function NoSummaryNotice() {
  return (
    <div className="rounded-xl border border-amber-400/20 bg-amber-400/5 px-5 py-4">
      <p className="font-medium text-amber-200">AI summary unavailable</p>
      <p className="mt-1 text-sm text-zinc-400">
        Your checkpoint was still saved. Your note, terminal output, and git changes are below: everything you need
        to pick up where you left off.
      </p>
    </div>
  )
}

function GitDetails({ git, defaultOpen }: { git: GitContext; defaultOpen: boolean }) {
  return (
    <details open={defaultOpen} className="group rounded-lg border border-zinc-800">
      <summary className="flex cursor-pointer list-none items-center justify-between px-4 py-3 text-sm text-zinc-400 select-none hover:text-zinc-200">
        <span>
          Git context
          <span className="ml-2 font-mono text-xs text-zinc-600">
            {git.changed_files.length} changed file{git.changed_files.length === 1 ? '' : 's'}
          </span>
        </span>
        <span className="text-zinc-600 transition-transform group-open:rotate-90" aria-hidden>
          ›
        </span>
      </summary>

      <div className="space-y-6 border-t border-zinc-800 px-4 py-4">
        {git.changed_files.length > 0 && (
          <ul className="space-y-1 font-mono text-sm">
            {git.changed_files.map((f) => (
              <li key={f.path} className="flex gap-3">
                <span className={`w-5 shrink-0 ${statusColor(f.status)}`}>{f.status}</span>
                <span className="truncate text-zinc-300">{f.path}</span>
              </li>
            ))}
          </ul>
        )}

        {git.recent_commits.length > 0 && (
          <div>
            <p className="mb-2 text-xs text-zinc-500">Recent commits</p>
            <ul className="space-y-1 font-mono text-sm text-zinc-400">
              {git.recent_commits.map((commit) => (
                <li key={commit} className="truncate">
                  {commit}
                </li>
              ))}
            </ul>
          </div>
        )}

        {(git.diff || git.diff_truncated) && (
          <div>
            <p className="mb-2 text-xs text-zinc-500">
              Diff{git.diff_truncated && <span className="text-amber-400/80"> · truncated</span>}
            </p>
            {git.diff && <Code wrap={false}>{git.diff}</Code>}
          </div>
        )}
      </div>
    </details>
  )
}

function statusColor(status: string): string {
  if (status === 'A' || status === '??') return 'text-emerald-400'
  if (status === 'D') return 'text-red-400'
  return 'text-amber-300'
}

function Code({
  children,
  tone = 'default',
  wrap = true,
}: {
  children: string
  tone?: 'default' | 'error'
  wrap?: boolean
}) {
  const toneClass =
    tone === 'error' ? 'border-red-500/20 bg-red-500/5 text-red-200' : 'border-zinc-800 bg-zinc-900/60 text-zinc-300'
  const wrapClass = wrap ? 'whitespace-pre-wrap break-words' : 'overflow-x-auto'
  return (
    <pre className={`rounded-lg border px-4 py-3 font-mono text-[13px] leading-relaxed ${wrapClass} ${toneClass}`}>
      {children}
    </pre>
  )
}
