import { checkpoints } from '../checkpoints'
import { LinkButton } from '../components/Button'
import { CheckpointCard } from '../components/CheckpointCard'
import { EmptyState, ErrorState, LoadingState } from '../components/States'
import { href, paths } from '../router'
import { useAsync } from '../useAsync'

const WORKFLOW = ['Choose repo', 'Save checkpoint', 'Resume later']

export function Dashboard() {
  const result = useAsync(() => checkpoints.list(), 'list')

  return (
    <div>
      <div className="mb-8">
        <div className="flex items-baseline justify-between gap-4">
          <h1 className="text-2xl font-semibold tracking-tight">Checkpoints</h1>
          {result.status === 'success' && result.data.length > 0 && (
            <span className="font-mono text-xs text-zinc-400">{result.data.length} saved</span>
          )}
        </div>
        <p className="mt-2 max-w-xl text-[15px] leading-relaxed text-zinc-400">
          Save your context before you step away. Resume captures your git changes and turns your note into a
          recovery plan, so you can pick up exactly where you left off.
        </p>
        <WorkflowSteps />
      </div>

      {result.status === 'loading' && <LoadingState variant="list" />}

      {result.status === 'error' && (
        <ErrorState title="Couldn't load checkpoints" message={result.error.message} onRetry={result.reload} />
      )}

      {result.status === 'success' && result.data.length === 0 && (
        <EmptyState
          title="No checkpoints yet"
          body="Before you step away, save a checkpoint. Resume records your branch, changed files, and diff, and AI writes the exact next step for when you come back."
          action={<LinkButton href={href(paths.new)}>Create your first checkpoint</LinkButton>}
        />
      )}

      {result.status === 'success' && result.data.length > 0 && (
        <ul className="space-y-2.5">
          {result.data.map((c) => (
            <li key={c.id}>
              <CheckpointCard checkpoint={c} />
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function WorkflowSteps() {
  return (
    <ol className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 sm:gap-x-2.5 text-sm text-zinc-300" aria-label="How Resume works">
      {WORKFLOW.map((step, i) => (
        <li key={step} className="flex items-center gap-2.5">
          {i > 0 && (
            <span className="hidden text-zinc-600 sm:inline" aria-hidden>
              →
            </span>
          )}
          <span className="flex items-center gap-2">
            <span className="grid h-5 w-5 place-items-center rounded-full border border-zinc-700 font-mono text-[11px] text-zinc-300">
              {i + 1}
            </span>
            {step}
          </span>
        </li>
      ))}
    </ol>
  )
}
