export function relativeTime(iso: string, now = Date.now()): string {
  const seconds = Math.round((now - new Date(iso).getTime()) / 1000)
  if (seconds < 45) return 'just now'
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.round(hours / 24)
  if (days < 7) return `${days}d ago`
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

export function fullDateTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

export function shortSha(sha: string): string {
  return sha.slice(0, 7)
}

export function basename(path: string): string {
  return path.replace(/\/+$/, '').split('/').pop() || path
}

// "https://www.fastapi.tiangolo.com/tutorial/" -> "fastapi.tiangolo.com/tutorial"
export function linkLabel(url: string): string {
  try {
    const u = new URL(url)
    const path = u.pathname.replace(/\/+$/, '')
    return u.hostname.replace(/^www\./, '') + path
  } catch {
    return url
  }
}
