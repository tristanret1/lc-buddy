---
name: job-add
description: Track a job posting in the pipeline — fetch the JD from a URL (or take a pasted one), score fit against jobs/profile.json, note the interview format and prep list, and record it with `lcb jobs add`. Use when the user pastes a job link, says "add this job", "track this role", "/job-add <url>".
allowed-tools: Bash, Read, Write, WebFetch, WebSearch
---

1. Read `jobs/profile.json` (level, locations, salary bar, stack, must_not, fit rubric) and, if present,
   `jobs/resume.md`. Don't ask the user for things the profile already answers.
2. Get the JD: `WebFetch` the URL (Greenhouse/Lever/Ashby/Workday/LinkedIn pages usually render; if blocked,
   ask the user to paste the text). Extract: company, title, location + remote policy, salary (if posted;
   Canadian postings in BC/ON often must list a range), level/years, stack, team/product, visa/work-auth line.
3. Score fit 0–5 with the profile's rubric and write a 2–3 line `fit_notes` that says *why* (which criteria
   hit/miss). Be honest: a US-only role is a 0 even if the stack is perfect.
4. Interview format: state what you know for this company (e.g. Amazon: OA 2 problems + work simulation,
   then loop of 4–5 rounds each 1 LP + 1 coding/design; Shopify: pair-programming + "life story"). If you
   don't know, say so and give the generic senior loop (coding ×2, system design, behavioural, hiring manager).
   Put 3–6 concrete prep items in `--prep` (semicolon-separated), referencing this repo's tools where they apply
   ("two more weeks of the Amazon list", "`/sd-daily` order-payment before the design round").
5. Record it:
   ```
   python3 -m lcb jobs add --company "..." --title "..." --url ... --location "..." --remote "remote-ca|hybrid-<city>|onsite-<city>|us-remote-ca-ok" \
     --salary "..." --level "..." --source "..." --fit N --fit-notes "..." --interview-format "..." --prep "a; b; c" \
     --status found|interested --next-action "apply by ..." --next-date YYYY-MM-DD
   ```
   Save the JD text to `jobs/jd/<id>.md` (title line, URL, fetched date, then the text) so it can be re-read
   before interviews.
6. Reply with: the fit score and why, the one thing that would move it up or down, and the next action with a
   date. If fit ≤ 1, say so plainly and ask whether to track it anyway.
