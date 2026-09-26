import { useEffect, useRef, useState, type ReactNode } from 'react'
import { api } from '../api'

// Voice thought dump: record up to a minute, get it transcribed, review/edit before saving.
// The transcript value lives in the parent (it's what gets submitted); this component owns the
// recording lifecycle. Voice is optional: every failure leaves the rest of the form untouched.

const MAX_SECONDS = 60
const MIN_BYTES = 1024 // mirrors the backend's limits so obvious failures skip the network
const MAX_BYTES = 5 * 1024 * 1024
// Chrome records audio/webm;codecs=opus, the primary supported path.
const PREFERRED_TYPES = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg;codecs=opus']

type VoiceState =
  | { kind: 'unsupported' }
  | { kind: 'idle' }
  | { kind: 'requesting' } // waiting for microphone permission
  | { kind: 'recording'; startedAt: number }
  | { kind: 'transcribing' }
  | { kind: 'error'; message: string }

const TYPE_INSTEAD = 'You can type your note instead.'

function isSupported(): boolean {
  return typeof MediaRecorder !== 'undefined' && typeof navigator !== 'undefined' && !!navigator.mediaDevices?.getUserMedia
}

function pickMimeType(): string | undefined {
  return PREFERRED_TYPES.find((type) => {
    try {
      return MediaRecorder.isTypeSupported(type)
    } catch {
      return false
    }
  })
}

function micErrorMessage(e: unknown): string {
  switch (e instanceof DOMException ? e.name : '') {
    case 'NotAllowedError':
    case 'SecurityError':
      return `Microphone access was blocked. Allow it from the address bar, or just type your note.`
    case 'NotFoundError':
    case 'OverconstrainedError':
      return `No microphone was found. ${TYPE_INSTEAD}`
    case 'NotReadableError':
    case 'AbortError':
      return `The microphone is being used by another app. ${TYPE_INSTEAD}`
    default:
      return `Couldn't start recording. ${TYPE_INSTEAD}`
  }
}

function clock(seconds: number): string {
  const s = Math.min(Math.floor(seconds), MAX_SECONDS)
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

export function VoiceThought({
  transcript,
  onTranscriptChange,
  onBusyChange,
  disabled = false,
}: {
  transcript: string
  onTranscriptChange: (text: string) => void
  onBusyChange: (busy: boolean) => void
  disabled?: boolean
}) {
  const [state, setState] = useState<VoiceState>(() => (isSupported() ? { kind: 'idle' } : { kind: 'unsupported' }))
  const [elapsed, setElapsed] = useState(0)
  const [notice, setNotice] = useState<string | null>(null)

  const recorderRef = useRef<MediaRecorder | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const tickRef = useRef<number | undefined>(undefined)
  const limitRef = useRef<number | undefined>(undefined)
  const busyRef = useRef(false) // synchronous guard against double starts
  const cancelledRef = useRef(false) // set on unmount: discard audio instead of transcribing
  const mountedRef = useRef(true)

  const busy = state.kind === 'requesting' || state.kind === 'recording' || state.kind === 'transcribing'
  useEffect(() => onBusyChange(busy), [busy, onBusyChange])

  // Stops every microphone track and clears both timers. Safe to call more than once.
  function releaseMic() {
    window.clearInterval(tickRef.current)
    window.clearTimeout(limitRef.current)
    tickRef.current = undefined
    limitRef.current = undefined
    streamRef.current?.getTracks().forEach((track) => track.stop())
    streamRef.current = null
  }

  useEffect(() => {
    mountedRef.current = true
    return () => {
      // Leaving the page mid-recording: stop, release the mic, and never transcribe.
      mountedRef.current = false
      cancelledRef.current = true
      const recorder = recorderRef.current
      if (recorder && recorder.state !== 'inactive') {
        try {
          recorder.stop()
        } catch {
          // Already stopping; the tracks are released below either way.
        }
      }
      releaseMic()
    }
    // Refs only; runs once on mount/unmount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function fail(message: string) {
    busyRef.current = false
    if (mountedRef.current) setState({ kind: 'error', message })
  }

  async function start() {
    if (busyRef.current || disabled) return
    if (!isSupported()) return setState({ kind: 'unsupported' })
    busyRef.current = true
    cancelledRef.current = false
    setNotice(null)
    setState({ kind: 'requesting' })

    let stream: MediaStream
    try {
      // Permission is requested only here, on an explicit click.
      stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } })
    } catch (e) {
      return fail(micErrorMessage(e))
    }
    if (!mountedRef.current || cancelledRef.current) {
      stream.getTracks().forEach((track) => track.stop())
      return
    }
    streamRef.current = stream

    const mimeType = pickMimeType()
    let recorder: MediaRecorder
    try {
      recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream)
    } catch {
      releaseMic()
      return fail(`Couldn't start recording in this browser. ${TYPE_INSTEAD}`)
    }

    chunksRef.current = []
    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunksRef.current.push(e.data)
    }
    recorder.onstop = () => {
      releaseMic()
      recorderRef.current = null
      const blob = new Blob(chunksRef.current, { type: recorder.mimeType || mimeType || 'audio/webm' })
      chunksRef.current = []
      if (cancelledRef.current || !mountedRef.current) {
        busyRef.current = false
        return
      }
      void transcribe(blob)
    }
    recorder.onerror = () => {
      cancelledRef.current = true // don't transcribe a broken recording
      if (recorder.state !== 'inactive') recorder.stop()
      releaseMic()
      fail(`Recording failed. ${TYPE_INSTEAD}`)
    }

    recorderRef.current = recorder
    const startedAt = Date.now()
    recorder.start(1000) // collect data every second, so a stop always has audio to flush
    setElapsed(0)
    setState({ kind: 'recording', startedAt })
    tickRef.current = window.setInterval(() => setElapsed((Date.now() - startedAt) / 1000), 250)
    limitRef.current = window.setTimeout(() => {
      setNotice('Stopped at the 1-minute limit.')
      stop()
    }, MAX_SECONDS * 1000)
  }

  // Manual Stop and the 60s limit share this path. onstop releases the mic and transcribes.
  function stop() {
    window.clearInterval(tickRef.current)
    window.clearTimeout(limitRef.current)
    const recorder = recorderRef.current
    if (recorder && recorder.state !== 'inactive') {
      setState({ kind: 'transcribing' })
      recorder.stop()
    }
  }

  async function transcribe(blob: Blob) {
    if (blob.size < MIN_BYTES) return fail(`That recording was too short. Try again, or just type your note.`)
    if (blob.size > MAX_BYTES) return fail(`That recording is too large to transcribe. ${TYPE_INSTEAD}`)
    setState({ kind: 'transcribing' })
    try {
      const { transcript: text } = await api.transcribe(blob)
      if (!mountedRef.current) return
      onTranscriptChange(text) // only a successful result replaces an earlier transcript
      busyRef.current = false
      setState({ kind: 'idle' })
    } catch (e) {
      fail(e instanceof Error ? e.message : `Couldn't transcribe the recording. ${TYPE_INSTEAD}`)
    }
  }

  function remove() {
    onTranscriptChange('')
    setNotice(null)
    if (state.kind === 'error') setState({ kind: 'idle' })
  }

  const hasTranscript = transcript.trim() !== ''
  const replacing = hasTranscript && busy

  return (
    <div className="mt-3 space-y-2.5">
      <div className="flex flex-wrap items-center gap-2" aria-live="polite">
        {state.kind === 'recording' ? (
          <>
            <span className="inline-flex items-center gap-2 text-sm text-zinc-200">
              <span className="relative flex h-2.5 w-2.5" aria-hidden>
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-red-400 opacity-60" />
                <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-red-500" />
              </span>
              Recording
              <span
                className={`font-mono text-xs tabular-nums ${elapsed >= MAX_SECONDS - 10 ? 'text-amber-300' : 'text-zinc-400'}`}
                aria-hidden
              >
                {clock(elapsed)} / {clock(MAX_SECONDS)}
              </span>
            </span>
            <VoiceButton onClick={stop} tone="stop">
              <StopIcon /> Stop
            </VoiceButton>
          </>
        ) : state.kind === 'requesting' ? (
          <span className="text-sm text-zinc-400">Waiting for microphone permission…</span>
        ) : state.kind === 'transcribing' ? (
          <span className="inline-flex items-center gap-2 text-sm text-zinc-400">
            <Spinner /> Transcribing your thought…
          </span>
        ) : (
          <>
            <VoiceButton onClick={start} disabled={disabled || state.kind === 'unsupported'}>
              <MicIcon /> {hasTranscript ? 'Record again' : 'Record thought'}
            </VoiceButton>
            {hasTranscript && (
              <VoiceButton onClick={remove} disabled={disabled}>
                Remove
              </VoiceButton>
            )}
            {!hasTranscript && state.kind !== 'unsupported' && state.kind !== 'error' && (
              <span className="text-xs text-zinc-500">Or say it out loud, up to a minute. You can edit it before saving.</span>
            )}
          </>
        )}
      </div>

      {state.kind === 'unsupported' && (
        <p className="text-xs text-zinc-500">Voice recording isn't available in this browser. {TYPE_INSTEAD}</p>
      )}
      {state.kind === 'error' && (
        <p role="alert" className="text-xs leading-relaxed text-red-300">
          {state.message}
          {hasTranscript && ' Your previous voice thought was kept.'}
        </p>
      )}
      {notice && state.kind !== 'error' && <p className="text-xs text-zinc-500">{notice}</p>}

      {hasTranscript && (
        <div className={replacing ? 'opacity-50' : ''}>
          <label htmlFor="voice-transcript" className="mb-1 flex items-center gap-2 text-xs font-medium text-zinc-400">
            <span className="text-emerald-400" aria-hidden>
              ✓
            </span>
            Voice thought
            <span className="font-normal text-zinc-500">
              {replacing ? 'recording a replacement…' : 'transcribed. Edit anything that was misheard'}
            </span>
          </label>
          <textarea
            id="voice-transcript"
            rows={3}
            value={transcript}
            onChange={(e) => onTranscriptChange(e.target.value)}
            readOnly={busy}
            className={
              'w-full resize-y rounded-lg border border-zinc-800 bg-zinc-900/40 px-3.5 py-2.5 text-[15px] text-zinc-200 ' +
              'transition-colors focus:border-emerald-400/60 focus:outline-none focus:ring-2 focus:ring-emerald-400/15'
            }
          />
        </div>
      )}
    </div>
  )
}

// type="button" everywhere: voice controls must never submit the checkpoint form.
function VoiceButton({
  onClick,
  disabled,
  tone = 'default',
  children,
}: {
  onClick: () => void
  disabled?: boolean
  tone?: 'default' | 'stop'
  children: ReactNode
}) {
  const tones = {
    default: 'border-zinc-800 text-zinc-300 hover:border-zinc-700 hover:bg-zinc-900 hover:text-zinc-100',
    stop: 'border-red-500/30 text-red-200 hover:border-red-400/50 hover:bg-red-500/10',
  }
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={
        `inline-flex h-8 items-center gap-1.5 rounded-md border px-3 text-sm font-medium transition-colors ${tones[tone]} ` +
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/60 disabled:pointer-events-none disabled:opacity-50'
      }
    >
      {children}
    </button>
  )
}

function MicIcon() {
  return (
    <svg viewBox="0 0 16 16" className="h-3.5 w-3.5" fill="none" aria-hidden>
      <rect x="5.5" y="1.75" width="5" height="8" rx="2.5" stroke="currentColor" strokeWidth="1.25" />
      <path d="M3.5 7.5a4.5 4.5 0 0 0 9 0M8 12v2.25" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" />
    </svg>
  )
}

function StopIcon() {
  return (
    <svg viewBox="0 0 16 16" className="h-3 w-3" aria-hidden>
      <rect x="3" y="3" width="10" height="10" rx="1.5" fill="currentColor" />
    </svg>
  )
}

function Spinner() {
  return (
    <svg viewBox="0 0 16 16" className="h-3.5 w-3.5 animate-spin" fill="none" aria-hidden>
      <circle cx="8" cy="8" r="6" stroke="currentColor" strokeOpacity="0.3" strokeWidth="2" />
      <path d="M14 8a6 6 0 0 0-6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  )
}
