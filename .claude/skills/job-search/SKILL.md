---
name: job-search
description: Web-search for open roles matching jobs/profile.json (level, Canada / Canada-OK remote, salary bar, stack) and present a shortlist with links and a fit guess; the user picks, then /job-add tracks them. Use when the user says "find jobs", "search roles", "what's open", "/job-search [extra criteria]".
allowed-tools: Bash, Read, WebSearch, WebFetch
---

Web search is lossy: job boards have no stable API, listings expire, salaries are often missing. Treat results
as leads, say so once, and never invent a posting you did not open.

1. Read `jobs/profile.json` and `jobs/pipeline.json` (skip companies already tracked unless the role differs).
   Take any extra criteria from the user's message (e.g. "fintech", "Go", "Toronto hybrid").
2. Run 4–8 `WebSearch` queries in one turn, mixing:
   - ATS-hosted postings: `site:boards.greenhouse.io "senior software engineer" canada remote`,
     `site:jobs.lever.co ...`, `site:jobs.ashbyhq.com ...`, `site:myworkdayjobs.com ...`
   - Aggregators that list remote-Canada roles: `"remote" "Canada" "senior software engineer" 2026`,
     `site:linkedin.com/jobs ... Canada remote`, `site:wellfound.com ...`
   - Careers pages of the employers listed in the profile's `watch_companies` (if any).
   Use `mode: "extended"` when a standard pass comes back thin.
3. Open the 5–10 most promising with `WebFetch` to confirm: still open, location/remote line, salary, level.
   Drop anything US-only without a Canada line, junior, or contract.
4. Present a table: company · role · location/remote · salary (or "not posted") · level · fit guess 0–5 ·
   link · one-line why. Rank by fit, then salary. 5–10 rows; fewer is fine if that's what's real.
5. Ask which to track; for each pick run the `/job-add` flow (fetch, score, record). Offer to set a
   follow-up `--next-date` for each application.
6. Append a line to `jobs/search-log.md`: date, criteria, queries that worked, roles added. Next time read it
   first so searches don't repeat.
