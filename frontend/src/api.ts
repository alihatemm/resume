import type { Checkpoint, CheckpointCreate, CheckpointListItem, GitContext, Health, SinceYouLeft } from './types'

// All calls go through the relative /api path (proxied to FastAPI by Vite in dev).

// Reads hit SQLite and return instantly. Create runs git capture plus Gemini, which the
// backend caps at ~15s, so its timeout leaves generous headroom.
const READ_TIMEOUT_MS = 10_000
const CREATE_TIMEOUT_MS = 60_000
// Transcription: upload plus the backend's ~15s Gemini budget, with headroom.
const TRANSCRIBE_TIMEOUT_MS = 30_000

const UNREACHABLE = 'Could not reach the Resume backend. Is the API server running?'

export class ApiError extends Error {
  readonly status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init: RequestInit = {}, timeoutMs = READ_TIMEOUT_MS): Promise<T> {
  let res: Response
  try {
    res = await fetch(path, { ...init, signal: AbortSignal.timeout(timeoutMs) })
  } catch (e) {
    if (e instanceof DOMException && e.name === 'TimeoutError') {
      throw new ApiError(0, `The backend didn't respond within ${Math.round(timeoutMs / 1000)}s.`)
    }
    throw new ApiError(0, UNREACHABLE)
  }

  if (!res.ok) {
    const body = await res.json().catch(() => null)
    // Our API always returns {"detail": "<string>"}. Anything else (e.g. the dev proxy's
    // own 5xx when FastAPI is down) means the backend isn't reachable.
    const detail = body && typeof body.detail === 'string' ? body.detail : null
    throw new ApiError(res.status, detail ?? (res.status >= 500 ? UNREACHABLE : `${res.status} ${res.statusText}`))
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

export const api = {
  health: () => request<Health>('/api/health'),

  inspectRepo: (path: string) => request<GitContext>(`/api/repo/inspect?path=${encodeURIComponent(path)}`),

  listCheckpoints: () => request<CheckpointListItem[]>('/api/checkpoints'),

  getCheckpoint: (id: number) => request<Checkpoint>(`/api/checkpoints/${id}`),

  // Git comparison against the repo's current state; loaded separately so it never blocks Restore.
  sinceCheckpoint: (id: number) => request<SinceYouLeft>(`/api/checkpoints/${id}/since`),

  // Raw recording as the request body (no base64, no multipart); Content-Type is the Blob's own type.
  transcribe: (audio: Blob) =>
    request<{ transcript: string }>(
      '/api/transcribe',
      { method: 'POST', headers: { 'Content-Type': audio.type }, body: audio },
      TRANSCRIBE_TIMEOUT_MS,
    ),

  createCheckpoint: (body: CheckpointCreate) =>
    request<Checkpoint>(
      '/api/checkpoints',
      { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) },
      CREATE_TIMEOUT_MS,
    ),
}
