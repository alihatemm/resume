# Resume: judging and submission package

> **Your computer remembers your files. Resume remembers your train of thought.**
> *Pick up exactly where you left off.*

Everything here describes what works on `main` today (tag `feature-complete-v1`).

---

## 1. Devpost description (~100 words)

Git remembers your code, not your train of thought. Resume is a save state for your head. Before you
step away, it captures your git changes and failing output, and you say where you are out loud: Gemini
transcribes your voice thought into editable text. Gemini then turns that raw context into a structured
recovery plan with one concrete NEXT STEP, while the backend computes and verifies the exact files and
lines that matter. When you return, Since You Left shows what changed in the repo, and one click on
**Resume work ↗** opens VS Code on the right line. Local-first, privacy-conscious, and not a chatbot.

## 2. 30-second elevator pitch

> Your computer remembers your files. Resume remembers your train of thought.
>
> Before an interruption, save a checkpoint: say where you are out loud, or type a short note. Gemini
> reads your voice thought, your diff, and your errors, and writes a recovery plan with the exact next
> step. When you come back, one click opens VS Code on the exact line. No chat window. Just pick up
> exactly where you left off.

## 3. 90-second live demo script

**Setup before judges arrive:** follow [`demo/DEMO.md`](../demo/DEMO.md) → *Setup*. Run
`scripts/reset_demo.sh`, start the demo backend with `RESUME_DB_PATH="$HOME/resume-demo/resume-demo.db"`,
start the frontend, and create **one backup checkpoint**. While doing that:

- Click **Record thought** once and allow the microphone for `localhost:5173` in Chrome.
- Click **Open ↗** once and tick Chrome's "Always allow" for VS Code.
- Put the terminal fixture on the clipboard: `pbcopy < demo/terminal.txt`.

| Time | On screen | Say |
|---|---|---|
| 0:00 | Terminal in `~/resume-demo/buggy-api`: run `pytest`, and one test fails | "Your computer remembers your files. Resume remembers your train of thought. Maya's test is failing, and she has to leave." |
| 0:08 | Browser: click **New checkpoint**. The repo path is prefilled: `✓ buggy-api · main · 1 changed file` | "She saves a checkpoint. Resume already read her branch and diff." |
| 0:13 | Click **Record thought**, speak the voice line below (about 7 s), click **Stop**. It shows **Transcribing your thought…** | *(voice line)* |
| 0:25 | The **Voice thought** field appears. Fix one word, then paste the terminal output | "Gemini transcribed it; she can fix anything misheard, and adds the failing output." |
| 0:32 | Click **Save**. The button shows **Creating checkpoint… Ns** | "Gemini now reads her words, the diff, and the error together." |
| 0:40 | Restore screen: point at the big **NEXT STEP** | "When she comes back, this is the first thing she sees: a recovery plan and one concrete next step." |
| 0:48 | Point at *Open these files* with line numbers | "The files and lines that matter. Gemini interprets; the paths and lines come from git, verified by our backend." |
| 0:55 | Point at the **Since You Left** strip | "Since You Left shows what changed in the repo since then." |
| 1:00 | Click **Resume work ↗** (label shows `app/middleware.py:25`). VS Code opens `app/middleware.py` at line 25 | "One click, and she's back in VS Code on the exact line." |
| 1:06 | Back to the browser | "Not a chatbot. Resume: pick up exactly where you left off." |

**Voice line to record** (say it naturally; exact wording doesn't matter):

> "I'm hardening the header sanitizer. Now GET /me returns 401, even though the test sends the
> Authorization header. Next I'd check the middleware."

The planned narration and actions take about 70 seconds, leaving about 20 seconds of buffer for
microphone permission, transcription, Gemini, and VS Code opening.

**Operator notes**

- Expected jump targets: `app/middleware.py` at **line 25** (the first changed line in the diff) and
  `tests/test_me.py` at **line 14** (from the traceback). **Resume work ↗** opens whichever file Gemini
  ranks first, and the label next to the button always shows the exact target.
- Don't rely on any exact generated sentence. Point at the NEXT STEP card, the files, and the line
  numbers, not at a particular phrase.
- **If the microphone is blocked or transcription fails:** Resume shows the reason and says you can type
  instead. Paste the note from `demo/DEMO.md` into **Where are you?** and continue. Say *"Voice is
  optional; typing works the same way."*
- **If the save shows "AI summary unavailable — showing basic recovery summary":** say *"If AI generation
  fails, the checkpoint still saves with a basic recovery summary"*, then go back and open the backup
  checkpoint to show the full AI plan.
- **If you see "Could not reach the Resume backend":** the demo backend isn't running (see `demo/DEMO.md`).
- **Between judges:** run `scripts/reset_demo.sh`. The saved checkpoints and their links keep working.

## 4. Three technical differentiators

1. **Grounded recovery summaries with server-verified file targets.** Gemini interprets the work context
   (diff, errors, typed note, voice transcript) and returns schema-validated JSON, choosing only from an
   allowlist of changed or mentioned files. File paths and line numbers are not taken from the model: the
   backend computes them from the terminal traceback or `git diff -U0` and verifies each file exists
   inside the repo. That's why **Resume work ↗** can jump straight to an exact line.
2. **Resilient AI step.** Summary generation and voice transcription share a 15-second budget policy.
   When a fallback model is configured, the primary gets at most 8 seconds so a slow failure can't starve
   the fallback. If AI generation fails, the checkpoint still saves with a basic recovery summary, clearly
   labeled, and the UI presents it as degraded rather than broken.
3. **Privacy-conscious capture.** It runs locally with SQLite storage and read-only git. Secret files are
   never read, tokens and keys are redacted before anything reaches Gemini, the diff and terminal output
   are size-capped, and the prompt treats all captured text as data, never as instructions. Voice audio is
   held in memory for the transcription request only, never written to disk, stored, or logged. Since You
   Left is pure git, with no AI.

## 5. Likely judge questions

**How is this different from a commit message or `git stash`?**
Those record *what* changed. Resume records *why* and *what's next*: your blocker, what you tried, the
real error, and the next action, linked to exact lines. It works on uncommitted, half-finished work,
which is exactly when you get interrupted.

**Why isn't this just a chatbot?**
There's no chat window and no prompting. You fill in one short form, or just talk for a few seconds, and
the result is a structured restore screen with a single NEXT STEP and one-click actions into your editor.

**How does Voice Thought Dump work?**
You click **Record thought** on New Checkpoint and talk for up to a minute. The browser records it,
the local backend sends the audio to Gemini for transcription, and the text appears in an editable
**Voice thought** field, separate from your typed note. When you save, the edited transcript goes into
the recovery context, where Gemini treats it as your own words. If the microphone is blocked or
transcription fails, you're told why and can type instead. Leaving the page mid-recording stops the
microphone and sends nothing.

**Do you store my voice recordings?**
No. The backend holds the audio in memory for the transcription request only; it's never written to
disk, stored, or logged. The transcript is redacted like other text and is stored only if you save the
checkpoint.

**What if Gemini hallucinates a file or line?**
File targets don't come from the model. Gemini can only pick from an allowlist of real changed or
mentioned files, and our backend computes every path and line itself, from git and the traceback, and
verifies the file exists inside the repo. Anything that can't be verified gets no Open action.

**What if Gemini is down or rate-limited?**
We try an optional fallback model inside a 15-second budget. If AI generation fails, the checkpoint still
saves with a basic recovery summary built from your note, voice transcript, and git state, and it's
labeled as a fallback. If transcription fails, you can type the note instead.

**What leaves my machine?**
When you record a voice thought: the audio, sent to Gemini for transcription. When you save: the repo
name, branch, HEAD, allowed file names, the last 5 commit subjects, your note, your voice transcript, the
terminal output you pasted, your links, and the diff. Secret files are skipped, secrets are redacted,
and inputs are size-capped. Storage is a local SQLite file, and Since You Left never calls AI. Resume is
local-first, not offline.

**What about prompt injection from code, terminal output, or speech?**
All captured content is wrapped in tagged data sections, and the instructions tell Gemini to treat it
strictly as data; the transcription prompt also ignores instructions spoken in the audio. On top of
that, the output is schema-validated and file locations are verified on the server, so injected text
can't redirect the jump.

**How does Since You Left work?**
Deterministic git on request: commits since the saved HEAD, whether history moved behind or diverged,
branch switches, and uncommitted files. It's read-only and bounded, and it never modifies the checkpoint.

**Does it work with other editors?**
Today restore links use VS Code's `vscode://file` URI. Other editors are a natural extension, since the
backend already produces verified absolute paths and line numbers.

**How did you test it?**
The backend has a pytest suite (158 passing) covering git capture, redaction, file locations, the AI
fallback paths, transcription, Since You Left, and the API. The frontend is type-checked and linted, and
Voice Thought Dump was verified end-to-end in Chrome: recording, transcription, editing, saving, the
permission-denied path, and leaving mid-recording. The demo repo is rebuilt identically by a script
before every judge.

**What's next?**
A save-state system for knowledge work: the same capture → recovery plan → one-click return loop, applied
beyond code.

## 6. Final demo and submission checklist

**Code and repo**

- [ ] `main` contains everything being demoed (`feature-complete-v1`).
- [ ] `(cd backend && .venv/bin/pytest)` passes.
- [ ] `(cd frontend && npm run build && npm run lint)` passes.
- [ ] `.env` is not committed (`git check-ignore .env` prints `.env`), and no keys appear in the repo or slides.
- [ ] README is up to date, and the repo link opens.

**Demo machine**

- [ ] `(cd backend && .venv/bin/python -m app.check_gemini)` ends with `parsed: ok=True`.
- [ ] `scripts/reset_demo.sh` runs cleanly.
- [ ] The demo backend is running with `RESUME_DB_PATH="$HOME/resume-demo/resume-demo.db"`, and the frontend is running.
- [ ] A backup checkpoint exists, and Chrome's "Open Visual Studio Code?" is set to **Always allow**.
- [ ] Chrome has microphone access for `localhost:5173`. A test recording transcribes, and the right input mic is selected.
- [ ] The room is quiet enough to record, or you have a backup plan: type the note from `demo/DEMO.md` instead.
- [ ] Clicking **Resume work ↗** and each **Open ↗** opens VS Code on the expected lines.
- [ ] The terminal fixture is on the clipboard (`pbcopy < demo/terminal.txt`).
- [ ] Browser zoom is readable from a distance, notifications are off, and the laptop is charged.

**Submission**

- [ ] Devpost description (section 1) pasted, with the tagline and the challenge ("What's Missing?") selected.
- [ ] Repo link added, plus any other materials the event requires.
- [ ] The whole team knows the 30-second pitch and the fallback line: *"If AI generation fails, the checkpoint still saves with a basic recovery summary."*
