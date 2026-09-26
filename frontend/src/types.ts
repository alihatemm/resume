// Mirrors backend/app/schemas.py. If you change one, change the other.

export interface ChangedFile {
  path: string
  status: string // e.g. "M", "A", "D", "??"
}

export interface GitContext {
  repo_name: string
  branch: string
  head_sha: string
  changed_files: ChangedFile[]
  recent_commits: string[]
  diff: string
  diff_truncated: boolean
}

export interface FileRef {
  path: string
  reason: string
  line: number | null // computed from the diff, never from the AI
  abs_path: string | null // used to build vscode://file/ links
}

export interface Link {
  title: string
  url: string
}

export interface Summary {
  title: string
  doing: string
  problem: string
  tried: string[]
  errors: string[]
  files: FileRef[]
  next_step: string
  next_step_detail: string
  links: Link[]
}

export interface CheckpointCreate {
  repo_path: string
  note?: string
  terminal_text?: string
  transcript?: string
  links?: string[]
}

export type CheckpointStatus = 'ready' | 'ai_failed'

export interface Checkpoint {
  id: number
  created_at: string // ISO 8601 UTC
  repo_path: string
  status: CheckpointStatus
  note: string
  terminal_text: string
  transcript: string
  git: GitContext
  summary: Summary | null
}

export interface CheckpointListItem {
  id: number
  created_at: string
  repo_path: string
  repo_name: string
  branch: string
  status: CheckpointStatus
  title: string
  next_step: string
}

export interface Health {
  status: string
  gemini_configured: boolean
  model: string
}

// Since you left: computed on request by GET /api/checkpoints/{id}/since, never stored.
export interface SinceCommit {
  sha: string // short
  subject: string
  author: string
  date: string // ISO 8601 author date
}

export interface SinceYouLeft {
  status: 'changed' | 'unchanged' | 'unavailable'
  reason: 'repo_missing' | 'not_a_repo' | 'commit_missing' | 'git_error' | null
  message: string // human-readable summary, safe to show as-is
  history: 'linear' | 'behind' | 'diverged'
  saved_head: string
  current_head: string | null
  saved_branch: string
  current_branch: string | null
  commits_ahead: number
  commits_behind: number
  commits: SinceCommit[] // newest first, bounded
  commits_truncated: boolean
  files_changed: number
  files: ChangedFile[] // bounded
  files_truncated: boolean
  uncommitted_files: number
  uncommitted_paths: string[] // bounded
}
