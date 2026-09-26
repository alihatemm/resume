import type { ReactNode } from 'react'
import { Button } from './Button'

function Bar({ className }: { className: string }) {
  return <div className={`rounded bg-zinc-800/70 ${className}`} />
}

export function LoadingState({ variant }: { variant: 'list' | 'detail' }) {
  return (
    <div className="animate-pulse" role="status" aria-label="Loading">
      {variant === 'list' ? (
        <div className="space-y-2.5">
          {[0, 1, 2].map((i) => (
            <div key={i} className="rounded-lg border border-zinc-800 px-4 py-4 sm:px-5">
              <Bar className="h-3 w-40 max-w-full" />
              <Bar className="mt-3 h-4 w-2/3" />
              <div className="mt-3 flex gap-2.5">
                <Bar className="h-4 w-10 shrink-0" />
                <Bar className="h-4 w-5/6" />
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div>
          <Bar className="h-3 w-56" />
          <Bar className="mt-4 h-7 w-3/4" />
          <div className="mt-8 rounded-xl border border-zinc-800 p-6">
            <Bar className="h-3 w-20" />
            <Bar className="mt-4 h-6 w-full" />
            <Bar className="mt-2 h-6 w-2/3" />
          </div>
          <Bar className="mt-10 h-3 w-24" />
          <Bar className="mt-3 h-14 w-full" />
          <Bar className="mt-2 h-14 w-full" />
        </div>
      )}
    </div>
  )
}

export function EmptyState({ title, body, action }: { title: string; body: string; action?: ReactNode }) {
  return (
    <div className="rounded-xl border border-dashed border-zinc-700 px-5 py-12 text-center sm:px-8 sm:py-14">
      <p className="text-base font-medium text-zinc-100">{title}</p>
      <p className="mx-auto mt-2 max-w-md text-[15px] leading-relaxed text-pretty text-zinc-400">{body}</p>
      {action && <div className="mt-6">{action}</div>}
    </div>
  )
}

export function ErrorState({
  title = 'Something went wrong',
  message,
  onRetry,
  action,
}: {
  title?: string
  message: string
  onRetry?: () => void
  action?: ReactNode
}) {
  return (
    <div role="alert" className="rounded-xl border border-red-500/25 bg-red-500/5 px-5 py-10 text-center sm:px-8">
      <p className="text-base font-medium text-red-300">{title}</p>
      <p className="mx-auto mt-2 max-w-md font-mono text-sm leading-relaxed break-words text-zinc-300">{message}</p>
      {(onRetry || action) && (
        <div className="mt-6 flex flex-wrap justify-center gap-2">
          {onRetry && (
            <Button variant="ghost" onClick={onRetry}>
              Try again
            </Button>
          )}
          {action}
        </div>
      )}
    </div>
  )
}
