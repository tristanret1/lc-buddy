---
name: resume-tailor
description: Produce a role-specific LaTeX resume from the base jobs/resume.tex for a tracked job — retargeted summary, reordered and re-emphasised bullets, matching keywords from the JD, nothing invented — saved as jobs/resumes/<job-id>.tex and linked in the pipeline. Use when the user says "tailor my resume for X", "resume for this job", "/resume-tailor <job-id>".
allowed-tools: Bash, Read, Write, Edit
---

Rules first, because they matter more than the template:
- **Never invent.** Every bullet in the tailored version must be traceable to a bullet in `jobs/resume.tex`
  or to something the user told you in this conversation. Re-emphasise, reorder, reword, cut. Do not add
  tools, numbers, titles or responsibilities that are not there. If the JD wants something the base resume
  lacks, say so in the reply instead of writing it in.
- Keep it to one page. The base is already full; every addition needs a cut.
- Keep the preamble and macros of `jobs/resume.tex` byte-identical; only edit content between
  `%%%%%% RESUME STARTS HERE` and `\end{document}`.

Steps:
1. `python3 -m lcb jobs show <id>` → read `jobs/jd/<id>.md`, `jobs/profile.json` (the `resume_flags`), and
   `jobs/resume.tex`. List the JD's top 6–8 must-have phrases (they are what the ATS and the recruiter scan for).
2. Decide the angle in one sentence ("agents + security, GPU as systems proof") and show it to the user with
   the plan: which bullets move up, which get reworded, which get cut, what the new summary says.
3. Write `jobs/resumes/<id>.tex`:
   - Summary: 3 sentences, each tied to a JD must-have, reusing the base resume's own numbers.
   - Experience: same jobs, same dates, same titles. Within a job, reorder bullets so the most relevant is
     first; reword to use the JD's vocabulary where the base resume says the same thing in other words
     (e.g. "detection rule DSL and dashboard for the SOC team" → add "user-facing" only if it was for users).
     Cut or shorten bullets irrelevant to this role to stay on one page.
   - Skills: reorder lines so the relevant category is first; do not add skills.
4. Compile check if a LaTeX engine exists (`which pdflatex tectonic`): `cd jobs/resumes && pdflatex -interaction=nonstopmode <id>.tex`
   and report errors; delete the .aux/.log/.out. If no engine, say so and ask the user to compile.
5. `python3 -m lcb jobs set <id> resume=jobs/resumes/<id>.tex` and note what changed:
   `python3 -m lcb jobs note <id> "resume tailored: <angle>"`.
6. Reply with: the angle, the summary text, a bullet list of what moved/changed/was cut, and anything the
   JD asked for that the resume genuinely cannot claim.
