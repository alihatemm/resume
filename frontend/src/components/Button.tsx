import type { AnchorHTMLAttributes, ButtonHTMLAttributes } from 'react'

type Variant = 'primary' | 'ghost'

const base =
  'inline-flex h-9 items-center justify-center gap-2 rounded-md px-3.5 text-sm font-medium whitespace-nowrap transition-colors ' +
  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/60 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950 ' +
  'disabled:pointer-events-none disabled:opacity-50'

const variants: Record<Variant, string> = {
  primary: 'bg-emerald-400 text-zinc-950 hover:bg-emerald-300',
  ghost: 'border border-zinc-800 text-zinc-300 hover:border-zinc-700 hover:bg-zinc-900 hover:text-zinc-100',
}

export function Button({
  variant = 'primary',
  className = '',
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return <button className={`${base} ${variants[variant]} ${className}`} {...props} />
}

export function LinkButton({
  variant = 'primary',
  className = '',
  ...props
}: AnchorHTMLAttributes<HTMLAnchorElement> & { variant?: Variant }) {
  return <a className={`${base} ${variants[variant]} ${className}`} {...props} />
}

export function Kbd({ children }: { children: string }) {
  return (
    <kbd className="rounded border border-current/25 px-1 font-mono text-[11px] leading-4 opacity-70">
      {children}
    </kbd>
  )
}
