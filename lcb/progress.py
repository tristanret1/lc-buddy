"""progress.json: per-problem state (keyed by slug), submission history, spaced repetition,
and the derived "interview readiness" numbers used by README/status."""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Optional

from .config import PROGRESS_FILE, load_config
from .problems import goal_count, in_target, load_list, ordered, problems, target_problems

EMPTY = {"problems": {}, "log": []}
DONE = ("solved", "mastered", "review_due")


def today() -> date:
    return date.today()


def iso(d: date) -> str:
    return d.isoformat()


def load() -> dict:
    if PROGRESS_FILE.exists():
        data = json.loads(PROGRESS_FILE.read_text())
        data.setdefault("problems", {})
        data.setdefault("log", [])
        return data
    return json.loads(json.dumps(EMPTY))


def save(data: dict) -> None:
    PROGRESS_FILE.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")


def entry(data: dict, slug: str) -> dict:
    return data["problems"].setdefault(slug, {
        "status": "todo", "started": None, "solved_at": None, "attempts": 0,
        "submissions": [], "srs": {"box": 0, "next_review": None, "reviews": 0},
        "reviewing": False, "review_attempts": 0, "notes": "", "confidence": None, "weak": False,
    })


def log(data: dict, event: str, slug: str, **extra) -> None:
    data["log"].append({"at": datetime.now().isoformat(timespec="seconds"), "event": event, "slug": slug, **extra})


# ---------- mutations ----------

def record_new(slug: str) -> dict:
    data = load()
    e = entry(data, slug)
    if e["status"] == "todo":
        e["status"] = "in_progress"
        e["started"] = iso(today())
        log(data, "new", slug)
    save(data)
    return e


def start_review(slug: str) -> dict:
    data = load()
    e = entry(data, slug)
    e["reviewing"] = True
    e["review_attempts"] = 0
    log(data, "review_start", slug)
    save(data)
    return e


def record_submission(slug: str, result: dict) -> dict:
    """result: normalised dict with keys status, runtime, memory, runtime_pct, memory_pct, id, url."""
    cfg = load_config()
    intervals = cfg["review_intervals"]
    data = load()
    e = entry(data, slug)
    accepted = result.get("status") == "Accepted"
    e["attempts"] += 1
    e["submissions"].append({"at": datetime.now().isoformat(timespec="seconds"), **result})
    e["submissions"] = e["submissions"][-20:]
    if e["status"] == "todo":
        e["status"], e["started"] = "in_progress", iso(today())

    weak_days = int(cfg.get("weak_interval", 1))
    if accepted:
        if e["reviewing"]:
            clean = e["review_attempts"] == 0
            box = e["srs"]["box"] + 1 if clean else max(0, e["srs"]["box"] - 1)
            e["srs"]["reviews"] += 1
            e["reviewing"], e["review_attempts"] = False, 0
            if box >= len(intervals):
                e["srs"].update(box=box, next_review=None)
                e["status"], e["weak"] = "mastered", False
            else:
                # a stumble makes it a 错题: re-check soon; a clean pass climbs the ladder
                days = weak_days if not clean else intervals[box]
                e["srs"].update(box=box, next_review=iso(today() + timedelta(days=days)))
                e["status"], e["weak"] = "solved", not clean
            log(data, "review_done", slug, clean=clean, box=box)
        elif e["status"] in ("in_progress", "todo"):
            struggled = e["attempts"] > 1  # needed a wrong submission first → 错题
            e["status"] = "solved"
            e["solved_at"] = iso(today())
            e["weak"] = struggled
            days = weak_days if struggled else intervals[0]
            e["srs"].update(box=0, next_review=iso(today() + timedelta(days=days)))
            log(data, "solved", slug, attempts=e["attempts"], weak=struggled)
        else:
            log(data, "resubmit", slug)
    else:
        if e["reviewing"]:
            e["review_attempts"] += 1
        log(data, "failed", slug, status=result.get("status"))
    save(data)
    return e


def skip_review(slug: str) -> dict:
    """Treat a due review as a clean pass without re-solving (the user knows it cold):
    climb one box on the same ladder as `record_submission`, or master it at the top.
    Note: 1456 was the first; use sparingly — it is self-attested, not verified."""
    cfg = load_config()
    intervals = cfg["review_intervals"]
    data = load()
    e = entry(data, slug)
    if e["status"] not in ("solved",):
        raise KeyError(f"{slug}: only a solved problem with a pending review can be skipped (status={e['status']})")
    box = e["srs"]["box"] + 1
    e["srs"]["reviews"] += 1
    e["reviewing"], e["review_attempts"], e["weak"] = False, 0, False
    if box >= len(intervals):
        e["srs"].update(box=box, next_review=None)
        e["status"] = "mastered"
    else:
        e["srs"].update(box=box, next_review=iso(today() + timedelta(days=intervals[box])))
    log(data, "review_skipped", slug, box=box)
    save(data)
    return e


def set_note(slug: str, note: str) -> None:
    data = load()
    entry(data, slug)["notes"] = note
    save(data)


def set_confidence(slug: str, level: int) -> None:
    """1-5 self rating. ≤2 marks the problem as 错题 (re-check after weak_interval days)."""
    cfg = load_config()
    data = load()
    e = entry(data, slug)
    e["confidence"] = max(1, min(5, int(level)))
    if e["confidence"] <= 2 and e["status"] in ("solved", "mastered"):
        e["weak"] = True
        e["status"] = "solved"
        nxt = iso(today() + timedelta(days=int(cfg.get("weak_interval", 1))))
        if not e["srs"].get("next_review") or e["srs"]["next_review"] > nxt:
            e["srs"]["next_review"] = nxt
    save(data)


# ---------- derived views ----------

def status_of(data: dict, slug: Optional[str]) -> str:
    e = data["problems"].get(slug) if slug else None
    if not e:
        return "todo"
    if e["status"] == "solved" and e["srs"].get("next_review") and e["srs"]["next_review"] <= iso(today()):
        return "review_due"
    return e["status"]


def due_reviews(data: Optional[dict] = None) -> list[dict]:
    """Everything whose forgetting-curve date has arrived. 错题 (weak) first, then oldest due first."""
    data = data or load()
    out = []
    for p in problems():
        if p.get("slug") and status_of(data, p["slug"]) == "review_due":
            e = data["problems"][p["slug"]]
            out.append({**p, "next_review": e["srs"]["next_review"], "box": e["srs"]["box"],
                        "weak": bool(e.get("weak")), "confidence": e.get("confidence")})
    out.sort(key=lambda x: (not x["weak"], x["next_review"]))
    return out


def failed_in_progress(data: Optional[dict] = None) -> list[dict]:
    """错题 of the other kind: attempted (wrong answer) but never accepted yet."""
    data = data or load()
    out = []
    for p in problems():
        e = data["problems"].get(p.get("slug") or "")
        if e and e["status"] == "in_progress" and e.get("attempts", 0) > 0:
            out.append({**p, "attempts": e["attempts"], "started": e.get("started")})
    return out


# ---------- category rotation ----------

def rotation_order(cfg: Optional[dict] = None) -> list[str]:
    cfg = cfg or load_config()
    rot = cfg.get("rotation") or {}
    keys = [L["key"] for L in load_list()["lists"]]
    if rot.get("order"):
        return [k for k in rot["order"] if k in keys]
    focus = cfg.get("focus") or []
    if focus:
        fk = [f.split(" / ")[0] for f in focus]
        return [k for k in dict.fromkeys(fk) if k in keys]
    return keys


def rotation_state(data: Optional[dict] = None, cfg: Optional[dict] = None) -> dict:
    """Round-robin over lists: each cycle asks for `block` new solves per list before moving on.
    Derived purely from solved counts, so it self-heals if you go off-plan.
    Returns {"current": key, "next": key, "block": n, "cycle": k, "lists": [{key,name,solved,target,in_block,done}]}."""
    data = data or load()
    cfg = cfg or load_config()
    block = max(1, int((cfg.get("rotation") or {}).get("block", 5)))
    order = rotation_order(cfg)
    rows = []
    for key in order:
        ps = [p for p in ordered(list_key=key) if in_target(p, cfg, ignore_focus=True)]
        solved = sum(1 for p in ps if status_of(data, p["slug"]) in DONE)
        rows.append({"key": key, "name": next((L["name"] for L in load_list()["lists"] if L["key"] == key), key),
                     "solved": solved, "target": len(ps), "level": solved // block,
                     "in_block": solved % block, "done": solved >= len(ps)})
    active = [r for r in rows if not r["done"]]
    if not active:
        return {"current": None, "next": None, "block": block, "cycle": 0, "lists": rows}
    level = min(r["level"] for r in active)
    cur = next(r for r in active if r["level"] == level)
    ci = active.index(cur)
    nxt = None
    for j in range(1, len(active) + 1):
        cand = active[(ci + j) % len(active)]
        if cand is not cur and cand["level"] <= level:
            nxt = cand
            break
    for r in rows:
        r["current"] = r is cur
    return {"current": cur["key"], "current_name": cur["name"], "next": nxt["key"] if nxt else None,
            "next_name": nxt["name"] if nxt else None, "block": block, "cycle": level + 1,
            "in_block": cur["in_block"], "lists": rows}


def plan(data: Optional[dict] = None, n_new: Optional[int] = None) -> dict:
    """Today's queue: 新题 (current category) → 错题 (weak reviews due, unfinished attempts) → 旧题 (reviews due)."""
    data = data or load()
    cfg = load_config()
    n_new = n_new or int(cfg["daily_new"])
    cap = int(cfg.get("daily_reviews", 2))
    rot_on = (cfg.get("rotation") or {}).get("enabled", True)
    rot = rotation_state(data, cfg) if rot_on else None
    if rot and rot["current"]:
        new = next_new(data, n_new, list_key=rot["current"])
        if not new:  # category exhausted mid-block → fall through to global order
            new = next_new(data, n_new)
    else:
        new = next_new(data, n_new)
    due = due_reviews(data)
    weak_due = [p for p in due if p["weak"]]
    old_due = [p for p in due if not p["weak"]]
    unfinished = failed_in_progress(data)
    reviews = (weak_due + old_due)[:cap]
    return {"rotation": rot, "new": new, "unfinished": unfinished, "weak": [p for p in reviews if p["weak"]],
            "old": [p for p in reviews if not p["weak"]], "deferred": max(0, len(due) - cap),
            "due_total": len(due), "in_progress": in_progress(data)}


def next_new(data: Optional[dict] = None, n: int = 1, list_key: Optional[str] = None,
             section: Optional[str] = None) -> list[dict]:
    data = data or load()
    cfg = load_config()
    picks = []
    seq = ordered(list_key, section) if (list_key or section) else target_problems(cfg)
    for p in seq:
        if not in_target(p, cfg, ignore_focus=True):
            continue
        if status_of(data, p["slug"]) == "todo":
            picks.append(p)
            if len(picks) >= n:
                break
    return picks


def in_progress(data: Optional[dict] = None) -> list[dict]:
    data = data or load()
    return [p for p in problems() if p.get("slug") and status_of(data, p["slug"]) == "in_progress"]


def stats(data: Optional[dict] = None) -> dict:
    data = data or load()
    cfg = load_config()
    plist = load_list()
    allp = plist["problems"]
    target = target_problems(cfg)
    target_slugs = {p["slug"] for p in target}
    goal = goal_count(cfg)

    counts = defaultdict(int)          # statuses over the target set
    solved_all = 0                     # any list problem accepted, target or not
    by_diff = {d: {"total": 0, "solved": 0} for d in ("Easy", "Medium", "Hard")}
    by_list: dict[str, dict] = {}
    solved_dates = []
    for L in plist["lists"]:
        by_list[L["key"]] = {"name": L["name"], "total": 0, "target": 0, "solved": 0, "sections": {}}
    for p in allp:
        st = status_of(data, p.get("slug"))
        done = st in DONE
        if done:
            solved_all += 1
            e = data["problems"][p["slug"]]
            if e.get("solved_at"):
                solved_dates.append(date.fromisoformat(e["solved_at"]))
        L = by_list.setdefault(p["list"], {"name": p["topic"], "total": 0, "target": 0, "solved": 0, "sections": {}})
        L["total"] += 1
        sec = L["sections"].setdefault(p["section"], {"total": 0, "target": 0, "solved": 0})
        sec["total"] += 1
        tgt = p.get("slug") in target_slugs
        if tgt:
            L["target"] += 1
            sec["target"] += 1
            counts[st] += 1
            d = by_diff.setdefault(p.get("difficulty") or "Medium", {"total": 0, "solved": 0})
            d["total"] += 1
            if done:
                d["solved"] += 1
        if done:
            L["solved"] += 1
            sec["solved"] += 1
    solved = counts["solved"] + counts["mastered"] + counts["review_due"]
    total = len(target)

    cutoff = today() - timedelta(days=14)
    recent = sum(1 for d in solved_dates if d > cutoff)
    actual_pace = recent / 14.0
    planned_pace = float(cfg["daily_new"])
    remaining = max(0, goal - solved)
    eta_actual = today() + timedelta(days=round(remaining / actual_pace)) if recent >= 3 and remaining else None
    eta_planned = today() + timedelta(days=round(remaining / planned_pace)) if planned_pace > 0 and remaining else None
    streak = _streak(data)

    # readiness (0-100), measured against `goal` rather than the whole list
    cov = min(1.0, solved / goal) if goal else 0.0
    mh_solved = by_diff["Medium"]["solved"] + by_diff["Hard"]["solved"]
    diff_score = min(1.0, mh_solved / (0.7 * goal)) if goal else 0.0
    # topic breadth: each list gets a share of the goal proportional to its target size
    shares = []
    for L in by_list.values():
        if L["target"] == 0:
            continue
        list_goal = goal * L["target"] / total if total else 0
        shares.append(min(1.0, L["solved"] / list_goal) if list_goal else 0.0)
    topic_score = sum(shares) / len(shares) if shares else 0.0
    overdue = counts["review_due"]
    retention = ((counts["mastered"] + counts["solved"]) / solved) if solved else 0.0
    readiness = round(100 * (0.40 * cov + 0.20 * diff_score + 0.20 * topic_score + 0.20 * retention * cov))

    return {
        "list_name": plist["name"], "total_all": len(allp), "total": total, "goal": goal,
        "solved": solved, "solved_all": solved_all, "mastered": counts["mastered"],
        "in_progress": counts["in_progress"], "todo": counts["todo"], "review_due": overdue,
        "by_difficulty": by_diff, "by_list": by_list,
        "recent_14d": recent, "actual_pace": actual_pace, "planned_pace": planned_pace, "remaining": remaining,
        "eta_actual": eta_actual, "eta_planned": eta_planned, "streak": streak, "readiness": readiness,
        "readiness_parts": {"coverage": cov, "difficulty": diff_score, "topics": topic_score, "retention": retention},
        "target_date": cfg.get("target_date"), "focus": cfg.get("focus") or [],
        "max_rating": cfg.get("max_rating"), "skip_premium": cfg.get("skip_premium", True),
    }


def _streak(data: dict) -> int:
    days = {ev["at"][:10] for ev in data["log"] if ev["event"] in ("solved", "review_done", "new", "failed")}
    d, n = today(), 0
    if iso(d) not in days:  # allow today to still be pending
        d -= timedelta(days=1)
    while iso(d) in days:
        n += 1
        d -= timedelta(days=1)
    return n


def recent_activity(data: Optional[dict] = None, n: int = 10) -> list[dict]:
    data = data or load()
    return list(reversed(data["log"][-n:]))
