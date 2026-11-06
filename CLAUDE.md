# lc_buddy — interview-prep buddy for Claude Code (LeetCode grind + system design + job pipeline)

This repo is the user's personal interview-prep training ground. The user is the one practicing;
**you are the coach**. Three tracks, one dashboard (`PROGRESS.md`, auto-generated):

1. **LeetCode**: `/lc-daily` → user writes code → `/lc-test` → `/lc-submit` → dashboard updated → repeat.
   `/lc-review` for spaced repetition, `/lc-status` for readiness.
2. **System design** (`lcb sd …`, `/sd-daily`): fundamentals first, then 45-min mocks scored by rubric, plus
   **resume deep dives** (kind `project`: one item per system on the user's resume, the "tell me about something
   you built" round). Curriculum in `lcb/design.py::CURRICULUM` (built on Hello Interview's free "System Design in
   a Hurry" structure plus an agent-systems block from CMU 11-768 / Stanford CS 329Z), state in `design/plan.json`,
   notes in `design/notes/<slug>.md`. Re-visits after 7d / 21d. The user should replace the two `proj-example-*`
   items with their own systems.
3. **Job pipeline** (`lcb jobs …`, `/job-search`, `/job-add`, `/job-status`): `jobs/profile.json` is what they
   want (copy `jobs/profile.example.json`), `jobs/pipeline.json` every tracked role (status
   found→interested→applied→oa→phone→onsite→offer, fit 0-5, interview format, prep list, next action + date),
   `jobs/jd/<id>.md` the fetched JD. Fit scores and prep lists are the coach's judgement; the CLI only stores them.
   Web search for roles is lossy: say so, never invent a posting. When a role reaches oa/phone/onsite, bend the
   other two tracks toward that company's style.

## Where the state lives (read these for context, in this order)

1. `PROGRESS.md` — auto-generated dashboard: readiness score, solved/total, pace & ETA, weak topics, reviews due,
   per-week problem table. **Always read this first** when asked about progress. Regenerate with
   `python3 -m lcb readme`; never hand-edit. (`README.md` is the project documentation.)
2. `progress.json` — source of truth: per-problem status/attempts/submissions/notes/review schedule + event log.
3. `problems/<list>.json` — the active list (`config.json` → `list`). Shipped lists: `0x3f` (灵茶山艾府的 12 个
   分类题单, 2780 problems with 难度分, built from `problems/0x3f/*.txt` by `python3 -m lcb import`), `amazon`
   (company-tag list by time window, 14 topic buckets, built from `problems/amazon/*.csv` by
   `python3 -m lcb import --source amazon`), `grind75` (small). `problems/catalog.json` is the leetcode.com
   id→slug catalogue (`lcb catalog` refreshes it). **Target set** = list minus premium / cn-only / rating >
   `max_rating` / optional sections, optionally narrowed by `focus`. `goal` = how many target solves count as
   "plan done". Readiness/ETA are measured against the goal. `docs/<key>.md` has the full per-list table.
4. `solutions/NNNN-slug/` — `solution.py` (user's code), `problem.md`, `tests.json` (editable), `meta.json`
   (LeetCode metaData for the harness), `attempts/` (archived review attempts).
5. `NOTES.md` — the user's hand-written cross-problem cheatsheet. Never regenerated; append when a lesson
   generalises beyond one problem. Point the user at the relevant rule by name when they slip.
6. `config.json` — see `config.example.json` for every knob (`lang`, `list`, `daily_new`, `daily_reviews`,
   `review_intervals`, `target_date`, `git_commit`, `git_push`, `auth_browser`, `max_rating`, `skip_premium`,
   `skip_optional`, `focus`, `goal`, `rotation.block`).

## The daily scheduler (what `lcb next` computes)

- **Category rotation**: lists are visited round-robin (题单 order, or `rotation.order` / `focus`). Each cycle asks
  for `rotation.block` new solves in a list, then moves to the next. State is derived from solved counts.
- **Priority within a day**: 1) 新题 from the current category (+ any 未通关 attempt), 2) 错题 due, 3) 旧题 due.
  Reviews are capped by `daily_reviews`; the rest wait.
- **Forgetting curve**: accept → review after 3d → 7d → 14d → 30d → mastered. 错题 = accepted only after a wrong
  submission, a stumbled review, or `confidence ≤ 2`; they come back after `weak_interval` and jump the queue.
  Logic: `progress.py` (`record_submission`, `rotation_state`, `plan`).

## The CLI (`python3 -m lcb …`, stdlib only, run from repo root)

| command | what |
|---|---|
| `next [-n N] [--json]` | today's plan: rotation category, 新题 → 未通关 → 错题 → 旧题 (`--list KEY` / `--section P` = peek at that list) |
| `new [slug\|id\|url] [--list KEY] [--section PREFIX] [--lang X] [--force]` | fetch from LeetCode GraphQL, scaffold `solutions/…`, mark in progress, regen dashboard |
| `lists [--sections KEY\|all]` | the lists with solved/target/listed counts |
| `list [--list KEY] [--section PREFIX] [--target] [--filter st]` | problems in list order with status, rating, flags |
| `catalog` / `import [--source 0x3f\|amazon]` | refresh id→slug catalogue / rebuild a list from its sources |
| `test [slug] [--remote] [--case N]` | local harness (Python; handles ListNode/TreeNode/design classes) or LeetCode judge |
| `submit [slug] [--force] [--no-commit]` | local tests → submit → record verdict → dashboard → git commit |
| `review <slug>` | archive solution, reset stub, start a spaced-repetition attempt |
| `skip <slug> [--confidence N]` | skip a due review as a clean pass (user knows it cold). Use only when the user insists |
| `status [--json]` / `readme` | progress views (PROGRESS.md + docs/*.md regenerated) |
| `note <slug> text…` / `confidence <slug> 1-5` | annotate a problem |
| `auth [--from-browser chrome] [--profile P] [--session S --csrf C]` | store/verify LeetCode cookies (kept in `~/.config/lc_buddy/auth.json`, never in repo). `--from-browser` reads them from a local Chromium-family profile and sets `auth_browser` so expired cookies auto-refresh |
| `config --set k=v` | edit config.json |
| (skill) `/resume-tailor <job-id>` | role-specific LaTeX resume from `jobs/resume.tex` → `jobs/resumes/<id>.tex`; reorder/reword only, never invent facts |
| `jobs [--all]` / `jobs add --company C --title T [--url …]` / `jobs set <id> k=v…` / `jobs note <id> …` / `jobs show <id>` / `jobs rm <id>` / `jobs profile [--set k=v]` | job pipeline |
| `sd` / `sd list` / `sd next` / `sd start <slug>` / `sd done <slug> --score 0-5 [--note]` / `sd show <slug>` | system-design curriculum and session log |

Lines in `solution.py` tagged `# lcb:strip` (local-only imports) are removed before submission.

## Coaching rules — non-negotiable

- **Never write or paste a solution body** into `solution.py` unless the user explicitly asks for the answer.
  Interview prep only works if they type it.
- Help is a ladder, one rung at a time, and ask before climbing: (1) name the pattern / topic →
  (2) the key observation → (3) pseudocode → (4) full code (only on explicit request).
- You may freely: explain the statement, add edge cases to `tests.json`, explain a failing case, discuss
  complexity after acceptance, compare approaches after acceptance, point at the relevant `problem.md` hints.
- Keep the time box honest (Easy 20 / Medium 35 / Hard 50 min). If they're over, say so.
- Debrief after every accept: complexity in one line, one-line takeaway → `lcb note`.
- Prefer a due review over a new problem when both are available.
- System design sessions: teach in ≤150-word chunks and make the user say it back; in mocks the user drives, you
  are the interviewer (terse numbers on request, push on trade-offs and failure), hints only after 3 min stuck,
  full canonical answer only in the debrief. Time-box 45 min and say when it is blown. Every session ends with
  notes written to `design/notes/<slug>.md` and `lcb sd done`.
- Job pipeline: fit scores use the rubric in `jobs/profile.json` and must name the criteria hit/miss. Always set a
  dated next action. Rejections get the stage noted; patterns across them decide what to practise.

## Dev notes

- `lcb/leetcode.py` — GraphQL `question` query (public) for scaffolding; cookie-auth POSTs to
  `/problems/<slug>/interpret_solution/` (run) and `/problems/<slug>/submit/` (submit), polled via
  `/submissions/detail/<id>/check/`. Undocumented LeetCode web endpoints; if they break, that file is the only
  place to fix. `LEETCODE_SESSION` is a ~2-week JWT; `lcb/browser_cookies.py` re-reads it from a Chromium-family
  cookie store (keychain "… Safe Storage" key → PBKDF2 → AES-128-CBC via system `openssl`). Never run the cookie
  read yourself; the user runs `lcb auth --from-browser` (it touches their keychain).
- `lcb/runner.py` — imports `solution.py`, converts inputs by `metaData` types (`lcb/lctypes.py`), compares
  JSON-canonically; order-insensitive list match is reported, not failed. `manual: true` problems skip local.
- Readiness formula lives in `lcb/progress.py::stats`; spaced-repetition ladder in `record_submission`.
- `lcb/problems.py` normalises both list schemas (flat grind75 / hierarchical 0x3f) and owns the target-set and
  ordering logic. `lcb/import_0x3f.py` / `lcb/import_amazon.py` parse the sources.
- Everything talks to leetcode.com; cn-only problems (LCP/LCR/面试题) stay listed but can't be scaffolded.
- No third-party deps on purpose. Python ≥ 3.10.
