"""Job pipeline: jobs/profile.json (what you're looking for) + jobs/pipeline.json (every role you track)
+ jobs/jd/<id>.md (the job description as fetched, for re-reading before an interview).

Statuses flow left to right; `rejected` / `withdrawn` / `stale` are terminal.
  found → interested → applied → oa → phone → onsite → offer
The fit score (0-5) and the interview-format notes are written by the coach after reading the JD
against the profile; the CLI only stores them.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime
from typing import Optional

from .config import ROOT

JOBS_DIR = ROOT / "jobs"
PROFILE_FILE = JOBS_DIR / "profile.json"
PIPELINE_FILE = JOBS_DIR / "pipeline.json"
JD_DIR = JOBS_DIR / "jd"

STATUSES = ["found", "interested", "applied", "oa", "phone", "onsite", "offer", "rejected", "withdrawn", "stale"]
ACTIVE = {"interested", "applied", "oa", "phone", "onsite"}
SETTABLE = {"status", "url", "location", "remote", "salary", "level", "source", "fit", "fit_notes",
            "interview_format", "prep", "resume", "next_action", "next_date", "company", "title"}
TERMINAL = {"offer", "rejected", "withdrawn", "stale"}

DEFAULT_PROFILE = {
    "level": "senior",                 # target level
    "years": 5,                        # years of experience to present
    "locations": ["Canada", "Remote (Canada)", "US remote, Canada-based OK"],
    "min_salary": 120000,
    "currency": "CAD",
    "salary_note": "120k+ is the bar; a strong role below it is still worth a look",
    "role_titles": ["Senior Software Engineer", "Software Engineer II/III", "Backend Engineer", "Full-stack Engineer"],
    "stack": [],                       # fill in: languages / frameworks / cloud you can interview in
    "domains": [],                     # e.g. SaaS, marketplaces, fintech
    "must_not": ["requires US work authorization with no remote option", "contract-only"],
    "resume": "jobs/resume.md",        # drop the resume here (markdown or plain text) for fit scoring
    "fit_rubric": {
        "5": "senior backend/full-stack, Canada or Canada-OK remote, stack overlap, salary ≥ bar",
        "4": "one of the above slightly off (e.g. salary unknown, mid-level title with senior scope)",
        "3": "two off, still worth applying",
        "2": "long shot: location or level is a stretch",
        "1": "only if nothing else",
        "0": "does not fit (wrong country, junior, contract)",
    },
}


# ---------- io ----------

def load_profile() -> dict:
    prof = dict(DEFAULT_PROFILE)
    if PROFILE_FILE.exists():
        prof.update(json.loads(PROFILE_FILE.read_text(encoding="utf-8")))
    return prof


def save_profile(prof: dict) -> None:
    JOBS_DIR.mkdir(exist_ok=True)
    PROFILE_FILE.write_text(json.dumps(prof, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_pipeline() -> dict:
    if PIPELINE_FILE.exists():
        return json.loads(PIPELINE_FILE.read_text(encoding="utf-8"))
    return {"jobs": []}


def save_pipeline(data: dict) -> None:
    JOBS_DIR.mkdir(exist_ok=True)
    PIPELINE_FILE.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


# ---------- crud ----------

def find(data: dict, token: str) -> dict:
    """Exact id, else unique prefix, else unique company match."""
    jobs = data["jobs"]
    for j in jobs:
        if j["id"] == token:
            return j
    pref = [j for j in jobs if j["id"].startswith(token)]
    if len(pref) == 1:
        return pref[0]
    comp = [j for j in jobs if _slug(j["company"]) == _slug(token)]
    if len(comp) == 1:
        return comp[0]
    if len(pref) > 1 or len(comp) > 1:
        raise KeyError(f"{token!r} is ambiguous: " + ", ".join(j["id"] for j in (pref or comp)))
    raise KeyError(f"no job matching {token!r}; see `lcb jobs`")


def add(company: str, title: str, **fields) -> dict:
    data = load_pipeline()
    base = f"{_slug(company)}-{_slug(title)[:40]}".strip("-")
    jid, n = base, 2
    while any(j["id"] == jid for j in data["jobs"]):
        jid, n = f"{base}-{n}", n + 1
    job = {
        "id": jid, "company": company, "title": title,
        "url": "", "location": "", "remote": "", "salary": "", "level": "", "source": "",
        "status": "found", "added": date.today().isoformat(), "updated": date.today().isoformat(),
        "fit": None, "fit_notes": "", "interview_format": "", "prep": [],
        "resume": "",                      # path of the tailored resume, e.g. jobs/resumes/<id>.tex
        "next_action": "", "next_date": None,
        "notes": [], "log": [{"at": _now(), "event": "added"}],
    }
    for k, v in fields.items():
        if v is not None and k in job:
            if k == "prep" and isinstance(v, str):
                v = [x.strip() for x in v.split(";") if x.strip()]
            job[k] = v
    if job["status"] not in STATUSES:
        raise KeyError(f"status must be one of {', '.join(STATUSES)}")
    data["jobs"].append(job)
    save_pipeline(data)
    return job


def set_fields(token: str, **fields) -> dict:
    data = load_pipeline()
    job = find(data, token)
    for k, v in fields.items():
        if v is None:
            continue
        if k not in SETTABLE:
            raise KeyError(f"cannot set {k!r}; settable: {', '.join(sorted(SETTABLE))}")
        if k == "status":
            if v not in STATUSES:
                raise KeyError(f"status must be one of {', '.join(STATUSES)}")
            if v != job["status"]:
                job["log"].append({"at": _now(), "event": "status", "from": job["status"], "to": v})
        if k == "fit":
            v = int(v)
        if k == "prep" and isinstance(v, str):
            v = [x.strip() for x in v.split(";") if x.strip()]
        job[k] = v
    job["updated"] = date.today().isoformat()
    save_pipeline(data)
    return job


def add_note(token: str, text: str) -> dict:
    data = load_pipeline()
    job = find(data, token)
    job["notes"].append({"at": _now(), "text": text})
    job["updated"] = date.today().isoformat()
    save_pipeline(data)
    return job


def remove(token: str) -> dict:
    data = load_pipeline()
    job = find(data, token)
    data["jobs"] = [j for j in data["jobs"] if j["id"] != job["id"]]
    save_pipeline(data)
    return job


# ---------- views ----------

def _due_flag(job: dict) -> str:
    d = job.get("next_date")
    if not d:
        return ""
    today = date.today().isoformat()
    return "‼️" if d < today else ("⏰" if d == today else "")


def board(show_all: bool = False) -> str:
    data = load_pipeline()
    jobs = data["jobs"]
    if not jobs:
        return ("pipeline is empty. Add one:\n  lcb jobs add --company 'Shopify' --title 'Senior Software Engineer' "
                "--url https://... --location 'Remote, Canada' --salary '150-180k CAD'\n"
                "or ask the coach: /job-add <url>, /job-search")
    out = []
    counts = {s: sum(1 for j in jobs if j["status"] == s) for s in STATUSES}
    out.append("  ".join(f"{s} {n}" for s, n in counts.items() if n))
    order = {s: i for i, s in enumerate(STATUSES)}
    rows = [j for j in jobs if show_all or j["status"] not in TERMINAL]
    rows.sort(key=lambda j: (-(j["status"] in ACTIVE), j.get("next_date") or "9999", -(j.get("fit") or 0), order[j["status"]]))
    out.append("")
    out.append(f"{'id':<40} {'status':<10} {'fit':<4} {'next':<12} action")
    for j in rows:
        fit = "-" if j.get("fit") is None else str(j["fit"])
        nxt = (j.get("next_date") or "") + _due_flag(j)
        out.append(f"{j['id'][:40]:<40} {j['status']:<10} {fit:<4} {nxt:<12} {j.get('next_action', '')}")
    if not show_all and any(j["status"] in TERMINAL for j in jobs):
        out.append(f"\n({sum(1 for j in jobs if j['status'] in TERMINAL)} closed; `lcb jobs --all` to show)")
    return "\n".join(out)


def show(token: str) -> str:
    data = load_pipeline()
    j = find(data, token)
    lines = [f"{j['company']} — {j['title']}  [{j['status']}]  fit {j.get('fit', '-')}",
             f"  {j.get('url', '')}",
             f"  location: {j.get('location', '')}   remote: {j.get('remote', '')}   salary: {j.get('salary', '')}   level: {j.get('level', '')}",
             f"  source: {j.get('source', '')}   added {j['added']}   updated {j['updated']}"]
    if j.get("fit_notes"):
        lines.append(f"  fit: {j['fit_notes']}")
    if j.get("interview_format"):
        lines.append(f"  interview: {j['interview_format']}")
    if j.get("prep"):
        lines.append("  prep: " + "; ".join(j["prep"]))
    if j.get("resume"):
        lines.append(f"  resume: {j['resume']}")
    if j.get("next_action"):
        lines.append(f"  next: {j['next_action']}  ({j.get('next_date') or 'no date'}) {_due_flag(j)}")
    for n in j.get("notes", []):
        lines.append(f"  • {n['at'][:10]} {n['text']}")
    jd = JD_DIR / f"{j['id']}.md"
    if jd.exists():
        lines.append(f"  JD: {jd.relative_to(ROOT)}")
    return "\n".join(lines)


def summary() -> dict:
    """For README / status: counts + what's due."""
    data = load_pipeline()
    jobs = data["jobs"]
    today = date.today().isoformat()
    due = [j for j in jobs if j.get("next_date") and j["next_date"] <= today and j["status"] not in TERMINAL]
    active = [j for j in jobs if j["status"] in ACTIVE]
    return {"total": len(jobs), "active": active, "due": due,
            "counts": {s: sum(1 for j in jobs if j["status"] == s) for s in STATUSES},
            "found": [j for j in jobs if j["status"] == "found"]}
