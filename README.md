# lc_buddy

A LeetCode + system-design + job-search **coach that lives inside [Claude Code](https://claude.com/claude-code)**.
You practise; the agent sets the table, keeps time, refuses to write your solution, grades you, and remembers
what you got wrong. Plain Python, no dependencies.

```
/lc-daily     today's problem (category rotation + spaced repetition), scaffolded into solutions/
/lc-test      run the example cases locally (or LeetCode's judge with --remote)
/lc-submit    submit to leetcode.com, record the verdict, regenerate the dashboard, git commit
/lc-review    re-solve a due problem from a blank stub (3d → 7d → 14d → 30d ladder; 错题 come back next day)
/lc-status    readiness score, weak topics, pace and ETA
/sd-daily     one system-design session: a fundamentals topic or a 45-min mock scored by rubric
/job-search   /job-add   /job-status   /resume-tailor     a small job pipeline with fit scoring
```

## Quick start

```bash
git clone <this repo> && cd lc_buddy
python3 -m lcb lists                      # the shipped problem lists
cp config.example.json config.json        # optional; defaults are sane
python3 -m lcb auth --from-browser chrome # LeetCode cookies from your browser (stays in ~/.config/lc_buddy/)
claude                                    # open Claude Code here, then: /lc-daily
```

`python3 -m lcb --help` lists every command; `CLAUDE.md` is the coach's brief and the full reference.

## What's inside

- **Problem lists** (`problems/`): 灵茶山艾府 (0x3f) 的 12 个分类题单 with 难度分 (2780 problems, transcribed from the
  public LeetCode lists), an Amazon company-tag list by time window (from
  [liquidslr/leetcode-company-wise-problems](https://github.com/liquidslr/leetcode-company-wise-problems)), and Grind 75.
  Target set = list minus premium / cn-only / rating cap / optional sections; `goal` is how many solves count as done.
- **Scheduler** (`lcb/progress.py`): round-robin over topic lists in blocks, then 错题 due, then 旧题 due; a
  forgetting-curve ladder per problem; readiness = coverage + difficulty + breadth + retention.
- **Local harness** (`lcb/runner.py`): runs your `solution.py` against `tests.json` using LeetCode's `metaData`
  types (ListNode, TreeNode, design classes). Add your own edge cases to `tests.json`.
- **System design** (`lcb/design.py`): a curriculum built on the structure of Hello Interview's free
  [System Design in a Hurry](https://www.hellointerview.com/learn/system-design/in-a-hurry/introduction) (framework
  → core concepts → key technologies → patterns → 30+ question breakdowns with difficulty/level), an agent-systems
  block (CMU 11-768, Stanford CS 329Z slides), and **resume deep dives** you fill in with your own systems. Items
  can point at your own offline copy of the HI pages via `LCB_HI_DIR`; nothing from HI is redistributed here.
- **Job pipeline** (`lcb/jobs.py`): `jobs/profile.json` (what you want), `jobs/pipeline.json` (every role, status,
  fit 0–5, prep list, dated next action), `jobs/jd/` (saved JDs). The agent scores fit and writes prep lists; the
  CLI only stores them.

## Coaching rules the agent follows

Never writes a solution body unless asked outright. Help is a ladder: pattern → key observation → pseudocode →
code, one rung at a time, and it asks before climbing. Time boxes are enforced (Easy 20 / Medium 35 / Hard 50).
Every accept gets a one-line debrief into `lcb note`. In design mocks you drive; it interviews. See `CLAUDE.md`.

## Files you own

`progress.json` (state), `solutions/`, `NOTES.md` (your cheatsheet), `config.json`, `jobs/*.json`, `jobs/resume.*`,
`design/notes/`. `PROGRESS.md` and `docs/` are regenerated. Credentials never enter the repo.

## License

MIT. Problem metadata belongs to LeetCode; list sources are credited above.
