import type { ReactNode } from 'react'
import { href, paths, type Route } from '../router'
import { Kbd, LinkButton } from './Button'

export function Layout({ route, children }: { route: Route; children: ReactNode }) {
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-10 border-b border-zinc-900 bg-zinc-950/85 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-3xl items-center justify-between px-4 sm:px-6">
          <a
            href={href(paths.dashboard)}
            className="flex items-center gap-2 rounded font-mono text-sm font-semibold tracking-tight text-zinc-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/60"
          >
            <span className="h-4 w-1.5 rounded-sm bg-emerald-400" aria-hidden />
            resume
          </a>
          {route.name !== 'new' && (
            <LinkButton href={href(paths.new)} className="h-8 px-3">
              New checkpoint <Kbd>N</Kbd>
            </LinkButton>
          )}
        </div>
      </header>
      <main className="mx-auto max-w-3xl px-4 pt-8 pb-24 sm:px-6 sm:pt-10">{children}</main>
    </div>
  )
}
