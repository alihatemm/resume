import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent, type ReactNode } from 'react'
import { checkpoints } from '../checkpoints'
import { Button, Kbd, LinkButton } from '../components/Button'
import { href, navigate, paths } from '../router'

const LAST_REPO_KEY = 'resume:last-repo-path'

function readLastRepo(): string {
  try {
    return localStorage.getItem(LAST_REPO_KEY) ?? ''
  } catch {
    return ''
  }
}

function saveLastRepo(path: string) {
  try {
    localStorage.setItem(LAST_REPO_KEY, path)
  } catch {
    // Storage unavailable; remembering the repo is only a convenience.
  }
}

function parseLinks(text: string): { links: string[]; invalid: string[] } {
  const lines = text
    .split(/\s+/)
    .map((l) => l.trim())
    .filter(Boolean)
  const isUrl = (s: string) => /^https?:\/\/\S+$/.test(s)
  return { links: lines.filter(isUrl), invalid: lines.filter((s) => !isUrl(s)) }
}

const inputClass =
  'w-full rounded-lg border border-zinc-800 bg-zinc-900/60 px-3.5 py-2.5 text-[15px] text-zinc-100 placeholder:text-zinc-600 ' +
  'transition-colors focus:border-emerald-400/60 focus:outline-none focus:ring-2 focus:ring-emerald-400/15'

export function NewCheckpoint() {
  const [repoPath, setRepoPath] = useState(readLastRepo)
  const [note, setNote] = useState('')
  const [terminal, setTerminal] = useState('')
  const [linksText, setLinksText] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [hadRepo] = useState(() => repoPath !== '')
  // A ref, not state, so a fast double ⌘↵ can't slip in before the re-render.
  const inFlight = useRef(false)
  const mounted = useRef(true)
  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
    }
  }, [])

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (inFlight.current) return

    const repo = repoPath.trim()
    if (!repo) return setError('Enter the path to your repository.')
    const { links, invalid } = parseLinks(linksText)
    if (invalid.length) return setError(`Not a valid URL: ${invalid[0]}`)

    setError(null)
    setSaving(true)
    inFlight.current = true
    try {
      // Can take several seconds: the backend generates the AI summary during create.
      const created = await checkpoints.create({ repo_path: repo, note, terminal_text: terminal, links })
      saveLastRepo(repo)
      // If the user left mid-create, the checkpoint still lands on the dashboard; don't yank them back.
      if (mounted.current) navigate(paths.detail(created.id))
    } catch (err) {
      if (!mounted.current) return
      setError(err instanceof Error ? err.message : 'Saving failed.')
      setSaving(false)
    } finally {
      inFlight.current = false
    }
  }

  function onKeyDown(e: KeyboardEvent<HTMLFormElement>) {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault()
      e.currentTarget.requestSubmit()
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-tight">New checkpoint</h1>
      <p className="mt-1 text-sm text-zinc-500">
        Your git state is captured automatically. Add a quick note so future you knows where to start.
      </p>

      <form onSubmit={submit} onKeyDown={onKeyDown} className="mt-8 space-y-6" noValidate aria-busy={saving}>
        <fieldset disabled={saving} className="space-y-6 transition-opacity disabled:opacity-50">
          <Field label="Repository" htmlFor="repo">
            <input
              id="repo"
              className={`${inputClass} font-mono text-sm`}
              placeholder="/Users/you/code/my-project"
              value={repoPath}
              onChange={(e) => setRepoPath(e.target.value)}
              autoFocus={!hadRepo}
              spellCheck={false}
              autoComplete="off"
            />
          </Field>

          <Field label="Where are you?" htmlFor="note" hint="What you were doing, what's broken, what you'd try next.">
            <textarea
              id="note"
              rows={4}
              className={`${inputClass} resize-y`}
              placeholder="page 2 of /users returns duplicates, think it's the offset math…"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              autoFocus={hadRepo}
            />
          </Field>

          <Field label="Terminal output" htmlFor="terminal" optional>
            <textarea
              id="terminal"
              rows={4}
              className={`${inputClass} resize-y font-mono text-[13px]`}
              placeholder="Paste a stack trace or failing test output"
              value={terminal}
              onChange={(e) => setTerminal(e.target.value)}
              spellCheck={false}
            />
          </Field>

          <Field label="Links" htmlFor="links" optional hint="One per line: docs, issues, Stack Overflow answers.">
            <textarea
              id="links"
              rows={2}
              className={`${inputClass} resize-y font-mono text-[13px]`}
              placeholder="https://…"
              value={linksText}
              onChange={(e) => setLinksText(e.target.value)}
              spellCheck={false}
            />
          </Field>
        </fieldset>

        {error && (
          <p role="alert" className="rounded-lg border border-red-500/20 bg-red-500/5 px-4 py-2.5 text-sm text-red-300">
            {error}
          </p>
        )}

        <div className="flex items-center gap-2 pt-2">
          <Button type="submit" disabled={saving} className={saving ? 'disabled:opacity-80' : ''}>
            {saving ? (
              <>
                <Spinner /> Creating checkpoint…
              </>
            ) : (
              <>
                Save checkpoint <Kbd>⌘↵</Kbd>
              </>
            )}
          </Button>
          {!saving && (
            <LinkButton variant="ghost" href={href(paths.dashboard)}>
              Cancel
            </LinkButton>
          )}
        </div>

        <p role="status" aria-live="polite" className="min-h-5 text-sm text-zinc-500">
          {saving && 'Capturing your work context and generating a recovery summary. This can take a few seconds.'}
        </p>
      </form>
    </div>
  )
}

function Field({
  label,
  htmlFor,
  hint,
  optional,
  children,
}: {
  label: string
  htmlFor: string
  hint?: string
  optional?: boolean
  children: ReactNode
}) {
  return (
    <div>
      <label htmlFor={htmlFor} className="mb-1.5 flex items-baseline gap-2 text-sm font-medium text-zinc-200">
        {label}
        {optional && <span className="text-xs font-normal text-zinc-600">optional</span>}
      </label>
      {children}
      {hint && <p className="mt-1.5 text-xs text-zinc-500">{hint}</p>}
    </div>
  )
}

function Spinner() {
  return (
    <svg viewBox="0 0 16 16" className="h-3.5 w-3.5 animate-spin" fill="none" aria-hidden>
      <circle cx="8" cy="8" r="6" stroke="currentColor" strokeOpacity="0.3" strokeWidth="2" />
      <path d="M14 8a6 6 0 0 0-6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  )
}
