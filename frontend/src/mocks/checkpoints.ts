import type { Checkpoint } from '../types'

// M1 mock data. Typed against the shared contract so any drift fails the build.
// Timestamps are relative to page load so "2h ago" stays realistic in demos.

function minutesAgo(minutes: number): string {
  return new Date(Date.now() - minutes * 60_000).toISOString()
}

export const mockCheckpoints: Checkpoint[] = [
  // ai_failed WITH a basic fallback summary (Gemini failed, backend built one from note + git).
  // Also exercises FileRef.line === null and FileRef.abs_path === null.
  {
    id: 6,
    created_at: minutesAgo(12),
    repo_path: '/Users/alex/code/buggy-api',
    status: 'ai_failed',
    note: 'login redirect loops back to /login after successful auth. session cookie is set but not read?',
    terminal_text: `$ pytest tests/test_auth.py
FAILED tests/test_auth.py::test_login_redirects_to_dashboard
E   AssertionError: assert '/login' == '/dashboard'`,
    transcript: '',
    git: {
      repo_name: 'buggy-api',
      branch: 'fix/login-redirect',
      head_sha: '5e8b1f3a9c2d7e40b6a1f8c3d5e92b7a4c0f1d68',
      changed_files: [
        { path: 'app/auth/session.py', status: 'M' },
        { path: 'app/routes/login.py', status: 'M' },
        { path: 'tests/test_auth.py', status: 'A' },
      ],
      recent_commits: ['5e8b1f3 Move session handling into app/auth', '9c41e7a Add page_size query param to /users'],
      diff: `diff --git a/app/auth/session.py b/app/auth/session.py
@@ -14,7 +14,7 @@ def set_session(response, user_id):
-    response.set_cookie("session", token, samesite="strict")
+    response.set_cookie("sid", token, samesite="strict")`,
      diff_truncated: false,
    },
    summary: {
      title: 'login redirect loops back to /login after successful auth',
      doing: 'login redirect loops back to /login after successful auth. session cookie is set but not read?',
      problem: '',
      tried: [],
      errors: ["AssertionError: assert '/login' == '/dashboard'"],
      files: [
        {
          path: 'app/auth/session.py',
          reason: 'Changed since last commit.',
          line: 17,
          abs_path: '/Users/alex/code/buggy-api/app/auth/session.py',
        },
        { path: 'app/routes/login.py', reason: 'Changed since last commit.', line: null, abs_path: null },
        {
          path: 'tests/test_auth.py',
          reason: 'New file.',
          line: null,
          abs_path: '/Users/alex/code/buggy-api/tests/test_auth.py',
        },
      ],
      next_step: 'Review your changes in app/auth/session.py, then rerun the failing test.',
      next_step_detail: 'Run `pytest tests/test_auth.py` to reproduce the failure.',
      links: [],
    },
  },
  {
    id: 5,
    created_at: minutesAgo(38),
    repo_path: '/Users/alex/code/buggy-api',
    status: 'ready',
    note: 'page 2 of /users returns the same people as page 1. pretty sure it is the offset math but the test still fails after my first fix. lunch.',
    terminal_text: `$ pytest tests/test_users.py -k pagination
FAILED tests/test_users.py::test_pagination_returns_distinct_pages
E   AssertionError: assert [21, 22, 23] == [11, 12, 13]
1 failed, 14 passed in 0.84s`,
    transcript: '',
    git: {
      repo_name: 'buggy-api',
      branch: 'fix/users-pagination',
      head_sha: '9c41e7a2b8d05f13c6e4a9b27f0d8e1c5a3b6f90',
      changed_files: [
        { path: 'app/routes/users.py', status: 'M' },
        { path: 'app/db.py', status: 'M' },
        { path: 'tests/test_users.py', status: 'M' },
      ],
      recent_commits: [
        '9c41e7a Add page_size query param to /users',
        '3f0b2d1 Seed 50 fake users for local dev',
        'b77e0c4 Initial FastAPI app',
      ],
      diff: `diff --git a/app/routes/users.py b/app/routes/users.py
@@ -39,7 +39,7 @@ def list_users(page: int = 1, page_size: int = 10):
-    offset = page * page_size
+    offset = page * page_size + 1
     rows = db.fetch_users(limit=page_size, offset=offset)
     return {"page": page, "items": rows}`,
      diff_truncated: false,
    },
    summary: {
      title: 'Fix duplicate rows in /users pagination',
      doing:
        'Fixing GET /users so that each page returns a distinct slice of users. Added a page_size param and a regression test.',
      problem:
        'Page 2 skips ahead by a full page. The offset is computed as page * page_size, which treats pages as zero-indexed while the API is one-indexed.',
      tried: [
        'Added +1 to the offset. Wrong direction: it shifts by one row, not one page',
        'Checked db.fetch_users. LIMIT/OFFSET are passed through correctly',
      ],
      errors: ['AssertionError: assert [21, 22, 23] == [11, 12, 13]'],
      files: [
        {
          path: 'app/routes/users.py',
          reason: 'Offset calculation lives here. This is the line to fix.',
          line: 42,
          abs_path: '/Users/alex/code/buggy-api/app/routes/users.py',
        },
        {
          path: 'tests/test_users.py',
          reason: 'Regression test that proves the fix.',
          line: 27,
          abs_path: '/Users/alex/code/buggy-api/tests/test_users.py',
        },
        {
          path: 'app/db.py',
          reason: 'Already verified; only revisit if the test still fails.',
          line: 18,
          abs_path: '/Users/alex/code/buggy-api/app/db.py',
        },
      ],
      next_step: 'Change the offset in list_users to (page - 1) * page_size and rerun the pagination test.',
      next_step_detail:
        'Revert the +1 you added on line 42 first. Then run `pytest tests/test_users.py -k pagination`; page 2 should start at user 11.',
      links: [
        { title: 'FastAPI: Query parameters', url: 'https://fastapi.tiangolo.com/tutorial/query-params/' },
        { title: 'SQLite LIMIT / OFFSET', url: 'https://www.sqlite.org/lang_select.html#limitoffset' },
      ],
    },
  },
  {
    id: 4,
    created_at: minutesAgo(3 * 60 + 12),
    repo_path: '/Users/alex/code/resume',
    // ai_failed WITHOUT a summary: raw-context fallback.
    status: 'ai_failed',
    note: 'hash router works, detail screen half done. need to handle summary === null case',
    terminal_text: `$ npm run build
src/screens/CheckpointDetail.tsx:48:22 - error TS18047: 'checkpoint.summary' is possibly 'null'.
Found 1 error.`,
    transcript: '',
    git: {
      repo_name: 'resume',
      branch: 'frontend',
      head_sha: 'e02e61a7d93c4b0f8a1e52c6b7d4f09a3e8c1b25',
      changed_files: [
        { path: 'frontend/src/screens/CheckpointDetail.tsx', status: '??' },
        { path: 'frontend/src/router.ts', status: '??' },
        { path: 'frontend/src/App.tsx', status: 'M' },
      ],
      recent_commits: [
        'e02e61a Expand README with full new-Mac setup',
        'e860da3 M0: project scaffold, shared schema, Gemini check',
      ],
      diff: `diff --git a/frontend/src/App.tsx b/frontend/src/App.tsx
@@ -1,12 +1,8 @@
-import { useEffect, useState } from 'react'
-import { api } from './api'
+import { useRoute } from './router'`,
      diff_truncated: false,
    },
    summary: null,
  },
  {
    id: 3,
    created_at: minutesAgo(26 * 60),
    repo_path: '/Users/alex/code/payments-service',
    status: 'ready',
    note: 'stripe webhook signature check fails only in staging. local works with stripe cli.',
    terminal_text: `stripe.error.SignatureVerificationError: No signatures found matching the expected signature for payload`,
    transcript: '',
    git: {
      repo_name: 'payments-service',
      branch: 'fix/webhook-signature',
      head_sha: '41ad0c9e7b2f6a8d3c5e1f04b9a7d62e8c3f5a17',
      changed_files: [
        { path: 'src/webhooks/stripe.ts', status: 'M' },
        { path: 'src/server.ts', status: 'M' },
      ],
      recent_commits: ['41ad0c9 Log raw webhook headers in staging', '8e2f71b Bump stripe to 16.x'],
      diff: `diff --git a/src/server.ts b/src/server.ts
@@ -12,6 +12,7 @@ const app = express()
 app.use(express.json())
+app.post('/webhooks/stripe', stripeWebhook)`,
      diff_truncated: false,
    },
    summary: {
      title: 'Stripe webhook signature fails in staging',
      doing: 'Debugging why Stripe webhook signature verification fails in staging but passes locally.',
      problem:
        'express.json() runs before the webhook route, so the handler receives a re-serialized body instead of the raw bytes Stripe signed.',
      tried: [
        'Rotated the staging webhook secret',
        'Confirmed STRIPE_WEBHOOK_SECRET is set in the staging env',
        'Logged raw headers: stripe-signature is present',
      ],
      errors: ['SignatureVerificationError: No signatures found matching the expected signature for payload'],
      files: [
        {
          path: 'src/server.ts',
          reason: 'Global express.json() is registered before the webhook route.',
          line: 13,
          abs_path: '/Users/alex/code/payments-service/src/server.ts',
        },
        {
          path: 'src/webhooks/stripe.ts',
          reason: 'Calls constructEvent with req.body.',
          line: 21,
          abs_path: '/Users/alex/code/payments-service/src/webhooks/stripe.ts',
        },
      ],
      next_step: 'Mount the Stripe route with express.raw({ type: "application/json" }) before the global JSON parser.',
      next_step_detail:
        'Move the app.post for /webhooks/stripe above app.use(express.json()) and pass express.raw() as route middleware so constructEvent gets the raw Buffer.',
      links: [{ title: 'Stripe: Check webhook signatures', url: 'https://docs.stripe.com/webhooks#verify-events' }],
    },
  },
  {
    id: 2,
    created_at: minutesAgo(2 * 24 * 60 + 90),
    repo_path: '/Users/alex/code/portfolio-site',
    status: 'ready',
    note: 'nav overlaps hero on mobile',
    terminal_text: '',
    transcript: '',
    git: {
      repo_name: 'portfolio-site',
      branch: 'main',
      head_sha: '7b3e9f1c2d8a4e6b0f5c3a9d1e7b2c8f4a6d0e3b',
      changed_files: [{ path: 'src/components/Nav.css', status: 'M' }],
      recent_commits: ['7b3e9f1 Sticky nav'],
      diff: `diff --git a/src/components/Nav.css b/src/components/Nav.css
@@ -1,4 +1,5 @@
 .nav {
+  position: fixed;
   top: 0;`,
      diff_truncated: false,
    },
    summary: {
      title: 'Fixed nav overlaps hero on mobile',
      doing: 'Making the site navigation sticky.',
      problem: 'With position: fixed, the nav no longer takes up space, so the hero slides underneath it on small screens.',
      tried: [],
      errors: [],
      files: [
        {
          path: 'src/components/Nav.css',
          reason: 'The position: fixed change that caused the overlap.',
          line: 2,
          abs_path: '/Users/alex/code/portfolio-site/src/components/Nav.css',
        },
      ],
      next_step: 'Switch the nav to position: sticky instead of fixed.',
      next_step_detail: 'Sticky keeps the nav in normal flow, so the hero stays below it without a magic padding value.',
      links: [],
    },
  },
  {
    id: 1,
    created_at: minutesAgo(6 * 24 * 60),
    repo_path: '/Users/alex/code/buggy-api',
    status: 'ready',
    note: 'rate limiter works per-process only',
    terminal_text: '',
    transcript: '',
    git: {
      repo_name: 'buggy-api',
      branch: 'feat/rate-limit',
      head_sha: 'c0d4a8e2f6b1937d5e0a4c8b2f6d1e9a3c7b5f02',
      changed_files: [
        { path: 'app/middleware/rate_limit.py', status: 'A' },
        { path: 'app/main.py', status: 'M' },
      ],
      recent_commits: ['c0d4a8e In-memory token bucket'],
      diff: '',
      diff_truncated: true,
    },
    summary: {
      title: 'Share rate-limit state across workers',
      doing: 'Adding a token-bucket rate limiter as FastAPI middleware.',
      problem: 'Buckets live in process memory, so with 4 uvicorn workers each client effectively gets 4x the limit.',
      tried: ['Ran with --workers 1 to confirm the limiter logic itself is correct'],
      errors: [],
      files: [
        {
          path: 'app/middleware/rate_limit.py',
          reason: 'Holds the in-memory bucket dict to replace.',
          line: 9,
          abs_path: '/Users/alex/code/buggy-api/app/middleware/rate_limit.py',
        },
        {
          path: 'app/main.py',
          reason: 'Where the middleware is registered.',
          line: null,
          abs_path: null,
        },
      ],
      next_step: 'Decide between Redis and SQLite for shared bucket state.',
      next_step_detail: 'Redis INCR with EXPIRE is the standard approach; SQLite avoids a new service for the demo.',
      links: [],
    },
  },
]
