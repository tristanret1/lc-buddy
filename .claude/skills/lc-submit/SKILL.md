---
name: lc-submit
description: Submit the current LeetCode solution to leetcode.com, record the verdict in progress.json, regenerate PROGRESS.md with updated readiness/progress, and git-commit. Use when the user says "submit", "ship it", "send to leetcode", "/lc-submit".
argument-hint: "[slug | id] [--force] [--no-commit]"
allowed-tools: Bash, Read
---

1. Make sure credentials exist: `python3 -m lcb auth`. If it fails, tell the user exactly how to fix it:
   log in at leetcode.com → DevTools → Application → Cookies → copy `LEETCODE_SESSION` and `csrftoken`,
   then `python3 -m lcb auth --session <...> --csrf <...>` (stored in `~/.config/lc_buddy/auth.json`,
   never in the repo). Do not ask the user to paste cookies into chat if they can run the command themselves
   (`! python3 -m lcb auth --session ... --csrf ...`).
2. Run `python3 -m lcb submit $ARGUMENTS`. It runs local tests first and refuses to submit if they are red
   (use `--force` only if the user insists). It then submits, polls the judge, records the result, regenerates
   PROGRESS.md and commits `solutions/<dir>`, `progress.json`, `PROGRESS.md`.
3. Report the verdict:
   - **Accepted**: runtime/memory percentiles, attempt count, when the spaced-repetition review is due.
     Then do a short debrief: ask the user to state time & space complexity in one line; confirm or correct.
     If the percentile is low (<30%), mention the optimal complexity class as a hint, not a rewrite.
     Offer `python3 -m lcb note <slug> "<one-line takeaway>"` and record it if they give one.
   - **Not accepted**: show the failing testcase, expected vs got. Coach — no fixes unless asked.
     Suggest adding that testcase to tests.json so `/lc-test` catches it.
4. Run `python3 -m lcb status` and give a one-line progress readout (solved X/75, readiness N, next up).
