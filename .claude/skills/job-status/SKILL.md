---
name: job-status
description: Show the job pipeline — counts by stage, roles with follow-ups due or overdue, what to do next, and update a role's status/notes on request. Use when the user asks "where am I with applications", "pipeline", "what's due", "mark X as applied", "/job-status".
allowed-tools: Bash, Read
---

1. `python3 -m lcb jobs` (board; `--all` to include closed). `python3 -m lcb jobs show <id>` for one role.
2. Summarise: active count by stage, anything ‼️ overdue or ⏰ due today, roles still at `found` with fit ≥ 4
   that haven't been applied to (that's the usual leak), and the next interview on the calendar.
3. Updates the user asks for:
   - `python3 -m lcb jobs set <id> status=applied next_action="follow up if silent" next_date=YYYY-MM-DD`
   - `python3 -m lcb jobs note <id> recruiter said ...`
   - `python3 -m lcb jobs set <id> status=rejected` — ask for the stage it died at and note it; patterns
     across rejections (always at OA? always at design?) decide what to practise.
4. When a role moves to `oa`/`phone`/`onsite`, re-read `jobs/jd/<id>.md` and the `prep` list, and turn it into
   a concrete plan with this repo: which list/section for `/lc-daily`, which `/sd-daily` topics, how many days.
5. One recommendation at the end, time-boxed: "apply to X today", "schedule the mock", "two more Amazon
   graph problems before Friday's OA".
