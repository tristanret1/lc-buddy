---
name: lc-status
description: Show LeetCode grind progress and interview readiness — solved counts, weak topics, pace/ETA, reviews due, what to do next. Use when the user asks "how am I doing", "progress", "am I ready", "how far from interview-ready", "/lc-status".
allowed-tools: Bash, Read
---

1. Run `python3 -m lcb status` (add `--json` if you need exact numbers); `python3 -m lcb lists` for the
   per-list view, `--sections KEY` to drill into one list.
2. Summarise in a few lines: readiness score and what it means, solved vs goal (and total solved), by
   difficulty, streak, pace vs plan and ETA, the 2–3 weakest lists, reviews due, and the next problem.
   Explain the target set if asked: list minus 会员题 / cn-only / rating above `max_rating`, narrowed by `focus`.
3. Give **one** concrete recommendation for today (a due review beats a new problem; a weak topic beats
   the next list item if the user has time for two).
4. If the user has an interview date, set it: `python3 -m lcb config --set target_date=YYYY-MM-DD`
   — PROGRESS.md then shows the required daily pace. Other knobs: `goal` (how many solves = done, default 300),
   `max_rating` (default 2200), `focus` (e.g. `'focus=["dp","binary-search"]'`), `skip_premium`.
5. PROGRESS.md holds the full picture (per-week tables, topic coverage); point the user to it rather than
   pasting it. Regenerate with `python3 -m lcb readme` if it looks stale.

Readiness formula (0–100): 40% coverage of the goal, 20% medium+hard solves vs 70% of goal, 20% topic
breadth (each list vs its proportional share of the goal), 20% retention (reviews done on schedule, scaled by coverage). Rough reading:
<15 just started · 15–40 foundations · 40–65 mid-way · 65–85 close · 85+ interview-ready.
