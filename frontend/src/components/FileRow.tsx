import { vscodeFileUri } from '../format'
import type { FileRef } from '../types'

// "Open" jumps to the file (and line) in VS Code using the backend-verified abs_path/line.
// line and abs_path may be null: no ":line" suffix, and no Open action without an absolute path.
export function FileRow({ file }: { file: FileRef }) {
  return (
    <li className="group flex items-center gap-3 rounded-lg border border-zinc-800 bg-zinc-900/50 px-4 py-3 transition-colors hover:border-zinc-700">
      <FileIcon />
      <div className="min-w-0 flex-1">
        <p className="truncate font-mono text-sm text-zinc-100" title={file.path}>
          {file.path}
          {file.line !== null && <span className="text-zinc-500">:{file.line}</span>}
        </p>
        {file.reason && <p className="mt-0.5 text-sm text-zinc-400">{file.reason}</p>}
      </div>
      {file.abs_path !== null && (
        <a
          href={vscodeFileUri(file.abs_path, file.line)}
          title={`Open in VS Code: ${file.path}${file.line !== null ? `:${file.line}` : ''}`}
          className="shrink-0 rounded-md border border-zinc-800 px-2.5 py-1 text-xs font-medium text-zinc-300 transition-colors group-hover:border-zinc-700 hover:bg-zinc-800 hover:text-white"
        >
          Open ↗
        </a>
      )}
    </li>
  )
}

function FileIcon() {
  return (
    <svg viewBox="0 0 16 16" className="h-4 w-4 shrink-0 text-zinc-500" fill="none" aria-hidden>
      <path
        d="M4 1.75h5.25L12.5 5v9.25H4z M9 1.75V5.25h3.5"
        stroke="currentColor"
        strokeWidth="1.25"
        strokeLinejoin="round"
      />
    </svg>
  )
}
