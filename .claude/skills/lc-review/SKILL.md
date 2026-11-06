---
name: lc-review
description: Spaced-repetition review of an already-solved LeetCode problem — archive the old solution, reset the stub, and have the user re-solve from scratch. Use when reviews are due ("/lc-status" shows 🔁) or the user says "review", "redo", "/lc-review".
argument-hint: "[slug | id]  (empty = the most overdue review)"
allowed-tools: Bash, Read
---

1. If no argument: `python3 -m lcb next --json` → take the plan's `weak` list first (错题), then `old`
   (旧题), in order. If both are empty, say so and suggest `/lc-daily` instead.
2. Run `python3 -m lcb review <slug>`. This moves the current `solution.py` to
   `solutions/<dir>/attempts/<date>.py` and rewrites a blank stub.
3. Show a compact statement (from `problem.md`) and set a tighter time box than the first time
   (Easy 15 / Medium 25 / Hard 40 min). Do **not** show or describe the archived solution.
4. The user solves, then `/lc-test` and `/lc-submit`. A clean accept (first submission) climbs the review
   ladder (3d → 7d → 14d → 30d → mastered) and clears the 错题 flag; needing a retry drops one rung and
   re-flags it as 错题 (re-check tomorrow). Low self-rating (`lcb confidence <slug> 2`) also flags it.
5. After acceptance, offer a diff-style comparison with the archived attempt: what got simpler, what
   they forgot. Keep it to 3 bullets.
