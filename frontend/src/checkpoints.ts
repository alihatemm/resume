import { basename, linkLabel } from './format'
import { mockCheckpoints } from './mocks/checkpoints'
import type { Checkpoint, CheckpointCreate, CheckpointListItem } from './types'

// M1: every checkpoint operation goes through this mock client.
// Later these map to the confirmed backend routes via `request()` in api.ts:
//   list -> GET /api/checkpoints, get -> GET /api/checkpoints/{id}, create -> POST /api/checkpoints
//
// Force a state from the URL for testing/demos (query goes before the hash):
//   /?mock=empty#/   no checkpoints
//   /?mock=error#/   every call fails
//   /?mock=slow#/    2.5s reads, 6s create (mimics Gemini running during POST)

type MockMode = 'normal' | 'empty' | 'error' | 'slow'

function mockMode(): MockMode {
  const mode = new URLSearchParams(window.location.search).get('mock')
  return mode === 'empty' || mode === 'error' || mode === 'slow' ? mode : 'normal'
}

const store: Checkpoint[] = mockMode() === 'empty' ? [] : [...mockCheckpoints]

export class NotFoundError extends Error {}

// Real creates are slow: the backend runs Gemini inside POST /api/checkpoints.
const DELAYS: Record<'read' | 'create', Record<'normal' | 'slow', number>> = {
  read: { normal: 350, slow: 2500 },
  create: { normal: 1500, slow: 6000 },
}

function respond<T>(produce: () => T, kind: 'read' | 'create' = 'read'): Promise<T> {
  const mode = mockMode()
  return new Promise((resolve, reject) => {
    setTimeout(
      () => {
        if (mode === 'error') return reject(new Error('Could not reach the Resume backend.'))
        try {
          resolve(produce())
        } catch (e) {
          reject(e)
        }
      },
      DELAYS[kind][mode === 'slow' ? 'slow' : 'normal'],
    )
  })
}

export function toListItem(c: Checkpoint): CheckpointListItem {
  return {
    id: c.id,
    created_at: c.created_at,
    repo_path: c.repo_path,
    repo_name: c.git.repo_name,
    branch: c.git.branch,
    status: c.status,
    title: c.summary?.title ?? '',
    next_step: c.summary?.next_step ?? '',
  }
}

// Stand-in for what the backend + AI would produce. Deliberately simple.
function buildMockCheckpoint(body: CheckpointCreate): Checkpoint {
  const note = body.note?.trim() ?? ''
  const terminal = body.terminal_text?.trim() ?? ''
  const repoName = basename(body.repo_path)
  const firstLine = note.split('\n')[0]
  const errors = terminal
    .split('\n')
    .filter((line) => /error|exception|failed/i.test(line))
    .slice(0, 3)

  return {
    id: Math.max(0, ...store.map((c) => c.id)) + 1,
    created_at: new Date().toISOString(),
    repo_path: body.repo_path,
    status: 'ready',
    note,
    terminal_text: terminal,
    transcript: body.transcript ?? '',
    git: {
      repo_name: repoName,
      branch: 'main',
      head_sha: 'a1b2c3d4e5f60718293a4b5c6d7e8f9012345678',
      changed_files: [],
      recent_commits: [],
      diff: '',
      diff_truncated: false,
    },
    summary: {
      title: firstLine ? firstLine.slice(0, 60) : `Work in ${repoName}`,
      doing: note || 'No note was captured.',
      problem: errors.length ? 'The terminal output contains errors.' : '',
      tried: [],
      errors,
      files: [],
      next_step: note ? `Pick up from your note: “${firstLine.slice(0, 80)}”` : `Reopen ${repoName} and review your last change.`,
      next_step_detail: 'This checkpoint was created with mock data. Real summaries arrive when the backend is connected.',
      links: (body.links ?? []).map((url) => ({ title: linkLabel(url), url })),
    },
  }
}

export const checkpoints = {
  list: (): Promise<CheckpointListItem[]> =>
    respond(() =>
      store
        .map(toListItem)
        .sort((a, b) => b.created_at.localeCompare(a.created_at)),
    ),

  get: (id: number): Promise<Checkpoint> =>
    respond(() => {
      const found = store.find((c) => c.id === id)
      if (!found) throw new NotFoundError(`Checkpoint #${id} doesn't exist.`)
      return found
    }),

  create: (body: CheckpointCreate): Promise<Checkpoint> =>
    respond(() => {
      const created = buildMockCheckpoint(body)
      store.unshift(created)
      return created
    }, 'create'),
}
