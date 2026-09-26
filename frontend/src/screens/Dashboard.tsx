import { checkpoints } from '../checkpoints'
import { LinkButton } from '../components/Button'
import { CheckpointCard } from '../components/CheckpointCard'
import { EmptyState, ErrorState, LoadingState } from '../components/States'
import { href, paths } from '../router'
import { useAsync } from '../useAsync'

export function Dashboard() {
  const result = useAsync(() => checkpoints.list(), 'list')

  return (
    <div>
      <div className="mb-6 flex items-baseline justify-between gap-4">
        <h1 className="text-2xl font-semibold tracking-tight">Checkpoints</h1>
        {result.status === 'success' && result.data.length > 0 && (
          <span className="font-mono text-xs text-zinc-500">{result.data.length} saved</span>
        )}
      </div>

      {result.status === 'loading' && <LoadingState variant="list" />}

      {result.status === 'error' && (
        <ErrorState title="Couldn't load checkpoints" message={result.error.message} onRetry={result.reload} />
      )}

      {result.status === 'success' && result.data.length === 0 && (
        <EmptyState
          title="No checkpoints yet"
          body="Save one before you step away: Resume captures your git state and notes so you can pick up exactly where you left off."
          action={<LinkButton href={href(paths.new)}>Create your first checkpoint</LinkButton>}
        />
      )}

      {result.status === 'success' && result.data.length > 0 && (
        <ul className="space-y-2">
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
