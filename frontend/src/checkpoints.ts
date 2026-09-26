import { api, ApiError } from './api'
import type { Checkpoint, CheckpointCreate, CheckpointListItem } from './types'

// Checkpoint operations, backed by the real FastAPI routes:
//   list -> GET /api/checkpoints, get -> GET /api/checkpoints/{id}, create -> POST /api/checkpoints
// mocks/checkpoints.ts is kept only as reference data and is not used by the app.

export class NotFoundError extends Error {}

export const checkpoints = {
  list: (): Promise<CheckpointListItem[]> => api.listCheckpoints(),

  get: async (id: number): Promise<Checkpoint> => {
    try {
      return await api.getCheckpoint(id)
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) throw new NotFoundError(`Checkpoint #${id} doesn't exist.`)
      throw e
    }
  },

  // Can take several seconds: the backend generates the AI summary during create.
  create: (body: CheckpointCreate): Promise<Checkpoint> => api.createCheckpoint(body),
}
