---
name: lc-test
description: Run the local example tests for a LeetCode solution in this repo (tests.json), or run LeetCode's own judge on those inputs with --remote. Use when the user says "test it", "run tests", "check my solution", "/lc-test".
argument-hint: "[slug | id] [--remote] [--case N]"
allowed-tools: Bash, Read, Edit
---

1. Run `python3 -m lcb test $ARGUMENTS`. With no slug it picks the single in-progress problem
   (or the most recently scaffolded one).
2. Report the result plainly: which cases passed/failed, expected vs got.
3. On failure, **coach, don't fix**:
   - Read the solution and identify *where* the logic diverges, describe it as a question or a hint
     ("what happens when both lists are empty?"), not as a patch.
   - Only edit `solution.py` if the user explicitly asks you to fix it.
   - You MAY add cases to `tests.json` (edge cases the user should be thinking about: empty input,
     single element, duplicates, negative numbers, max constraints). Follow the existing format:
     `input` = one string per parameter in LeetCode's JSON-ish format, `expected` = raw output string.
4. `expected: null` means the scaffolder couldn't parse the answer from the statement. Run
   `python3 -m lcb test <slug> --remote` — it uses LeetCode's judge and backfills the expected values
   into tests.json (needs cookies, see `/lc-submit`).
5. Problems marked `local: false` (custom judges, e.g. clone-graph, serialize-tree) can only be checked
   with `--remote`.
6. Order-insensitive matches are reported as such; remind the user the real judge may require exact order.
