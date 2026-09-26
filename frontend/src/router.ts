import { useEffect, useState } from 'react'

// Tiny hash router: three screens don't need a dependency.
// URLs look like `/#/`, `/#/new`, `/#/checkpoints/3`.

export type Route =
  | { name: 'dashboard' }
  | { name: 'new' }
  | { name: 'detail'; id: number }
  | { name: 'not_found' }

export function parseRoute(hash: string): Route {
  const path = hash.replace(/^#/, '') || '/'
  if (path === '/') return { name: 'dashboard' }
  if (path === '/new') return { name: 'new' }
  const match = path.match(/^\/checkpoints\/(\d+)$/)
  if (match) return { name: 'detail', id: Number(match[1]) }
  return { name: 'not_found' }
}

export const paths = {
  dashboard: '/',
  new: '/new',
  detail: (id: number) => `/checkpoints/${id}`,
}

export function href(path: string): string {
  return `#${path}`
}

export function navigate(path: string): void {
  window.location.hash = path
}

export function useRoute(): Route {
  const [route, setRoute] = useState(() => parseRoute(window.location.hash))

  useEffect(() => {
    const onChange = () => {
      setRoute(parseRoute(window.location.hash))
      window.scrollTo(0, 0)
    }
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])

  return route
}
