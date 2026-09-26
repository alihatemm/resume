import type { ReactNode } from 'react'

export function NextStepCard({ step, detail, action }: { step: string; detail: string; action?: ReactNode }) {
  return (
    <section
      aria-labelledby="next-step-label"
      className="relative overflow-hidden rounded-xl border border-emerald-400/25 bg-emerald-400/[0.07] px-6 py-6 sm:px-7 sm:py-7"
    >
      <div className="absolute inset-y-0 left-0 w-1 bg-emerald-400" aria-hidden />
      <p id="next-step-label" className="text-xs font-semibold tracking-[0.18em] text-emerald-400 uppercase">
        Next step
      </p>
      <p className="mt-3 text-xl leading-snug font-semibold tracking-tight text-balance text-white sm:text-2xl">
        {step}
      </p>
      {detail && (
        <p className="mt-3 max-w-prose text-[15px] leading-relaxed text-zinc-300">
          <InlineCode text={detail} />
        </p>
      )}
      {action && <div className="mt-6">{action}</div>}
    </section>
  )
}

// Renders `backticked` spans as code; summaries often include commands.
function InlineCode({ text }: { text: string }) {
  return text.split(/(`[^`]+`)/).map((part, i) =>
    part.startsWith('`') && part.endsWith('`') ? (
      <code key={i} className="rounded bg-zinc-800/80 px-1.5 py-0.5 font-mono text-[13px] text-zinc-100">
        {part.slice(1, -1)}
      </code>
    ) : (
      part
    ),
  )
}
