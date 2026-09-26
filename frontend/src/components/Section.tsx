import type { ReactNode } from 'react'

export function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section>
      <h2 className="mb-3 text-xs font-semibold tracking-wider text-zinc-500 uppercase">{title}</h2>
      {children}
    </section>
  )
}
