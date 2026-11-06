"""Problem lists (problems/<name>.json), the "target set" filter, and slug resolution.

Two list schemas are accepted and normalised to one shape:
  * flat (grind75.json): problems[] with id/slug/difficulty/topic/week
  * hierarchical (0x3f.json): lists[] with sections[] of ids + problems[] with rating/premium/cn_only/...
Every normalised problem has: id (str), slug (may be None for cn-only), title, title_en, difficulty,
rating, premium, cn_only, topic (list name), list (list key), section (path), note, order, also_in.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

from .config import PROBLEMS_DIR, SOLUTIONS_DIR, load_config


def list_path(name: Optional[str] = None) -> Path:
    name = name or load_config()["list"]
    p = PROBLEMS_DIR / f"{name}.json"
    if not p.exists():
        raise FileNotFoundError(f"problem list not found: {p}")
    return p


def _normalise(data: dict, key: str) -> dict:
    if "lists" in data:
        for p in data["problems"]:
            p["id"] = str(p["id"])
            p.setdefault("also_in", [])
            p.setdefault("note", "")
        return data
    # flat schema (Grind 75 style)
    sections: dict[str, list] = {}
    for i, p in enumerate(data["problems"]):
        p["id"] = str(p["id"])
        p.setdefault("title", None)
        p.setdefault("title_en", None)
        p.setdefault("rating", None)
        p.setdefault("premium", False)
        p.setdefault("cn_only", False)
        p.setdefault("note", "")
        p.setdefault("also_in", [])
        p["list"] = key
        p["section"] = f"Week {p['week']}" if p.get("week") else "Extra"
        p["order"] = i
        sections.setdefault(p["section"], []).append(p["id"])
    data["lists"] = [{"key": key, "name": data.get("name", key), "url": data.get("source", ""),
                      "count": len(data["problems"]),
                      "sections": [{"path": s, "ids": ids} for s, ids in sections.items()]}]
    return data


@lru_cache(maxsize=4)
def _load_cached(path_str: str, mtime: float) -> dict:
    p = Path(path_str)
    return _normalise(json.loads(p.read_text(encoding="utf-8")), p.stem)


def load_list(name: Optional[str] = None) -> dict:
    p = list_path(name)
    return _load_cached(str(p), p.stat().st_mtime)


def save_list(data: dict, name: Optional[str] = None) -> None:
    list_path(name).write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    _load_cached.cache_clear()


def problems(name: Optional[str] = None) -> list[dict]:
    return load_list(name)["problems"]


def by_slug(name: Optional[str] = None) -> dict[str, dict]:
    return {p["slug"]: p for p in problems(name) if p.get("slug")}


def by_id(name: Optional[str] = None) -> dict[str, dict]:
    return {p["id"]: p for p in problems(name)}


# ---------- ordering ----------

def ordered(list_key: Optional[str] = None, section: Optional[str] = None) -> list[dict]:
    """Problems in list/section order (deduplicated), optionally restricted to one list key
    and/or a section-path prefix. With no arguments this is the whole plan in reading order."""
    data = load_list()
    ids = by_id()
    seen, out = set(), []
    for L in data["lists"]:
        if list_key and L["key"] != list_key:
            continue
        for sec in L["sections"]:
            if section and not (sec["path"].startswith(section) or f"{L['key']} / {sec['path']}".startswith(section)):
                continue
            for i in sec["ids"]:
                if i in seen or i not in ids:
                    continue
                seen.add(i)
                out.append(ids[i])
    return out


def focus_ordered(focus: list[str]) -> list[dict]:
    """Concatenate the focus entries in the order given: "dp", "dp / 三、背包", or "三、背包"."""
    keys = {L["key"] for L in load_list()["lists"]}
    seen, out = set(), []
    for f in focus:
        if f in keys:
            chunk = ordered(list_key=f)
        elif " / " in f and f.split(" / ")[0] in keys:
            k, rest = f.split(" / ", 1)
            chunk = ordered(list_key=k, section=rest)
        else:
            chunk = ordered(section=f)
        for p in chunk:
            if p["id"] not in seen:
                seen.add(p["id"])
                out.append(p)
    return out


# ---------- target set ----------

def in_focus(p: dict, focus: list[str]) -> bool:
    if not focus:
        return True
    tags = [p["list"], f"{p['list']} / {p['section']}", p["section"], *p.get("also_in", [])]
    return any(t.startswith(f) or t == f for f in focus for t in tags)


def in_target(p: dict, cfg: Optional[dict] = None, ignore_focus: bool = False) -> bool:
    """The problems the plan actually expects you to solve."""
    cfg = cfg or load_config()
    if not p.get("slug") or p.get("cn_only"):
        return False
    if cfg.get("skip_premium", True) and p.get("premium"):
        return False
    if cfg.get("skip_optional", True) and "选做" in (p.get("section") or ""):
        return False  # 0x3f marks these sections optional; keep the rotation on the core material
    mr = cfg.get("max_rating")
    if mr and p.get("rating") and p["rating"] > mr:
        return False
    if not ignore_focus and not in_focus(p, cfg.get("focus") or []):
        return False
    return True


def target_problems(cfg: Optional[dict] = None, ignore_focus: bool = False) -> list[dict]:
    cfg = cfg or load_config()
    focus = cfg.get("focus") or []
    seq = focus_ordered(focus) if (focus and not ignore_focus) else ordered()
    return [p for p in seq if in_target(p, cfg, ignore_focus=True)]


def goal_count(cfg: Optional[dict] = None) -> int:
    """How many target problems count as 'done with the plan'."""
    cfg = cfg or load_config()
    total = len(target_problems(cfg))
    g = cfg.get("goal")
    if g:
        return min(int(g), total) if total else int(g)
    return total if total <= 150 else min(300, total)


# ---------- directories & slugs ----------

def dir_name(problem_id: int | str, slug: str) -> str:
    pid = str(problem_id)
    if pid.isdigit():
        return f"{int(pid):04d}-{slug}"
    return re.sub(r"[^A-Za-z0-9]+", "-", pid).strip("-").lower() + f"-{slug}"


def solution_dir(slug: str) -> Optional[Path]:
    """Find solutions/<prefix>-<slug> regardless of the numeric prefix."""
    if not SOLUTIONS_DIR.exists():
        return None
    for d in SOLUTIONS_DIR.iterdir():
        if d.is_dir() and (d / "meta.json").exists():
            try:
                if json.loads((d / "meta.json").read_text())["slug"] == slug:
                    return d
            except (json.JSONDecodeError, KeyError):
                pass
        if d.is_dir() and re.sub(r"^\d{4}-", "", d.name) == slug:
            return d
    return None


def resolve_slug(token: str) -> str:
    """Accept a slug, a frontend id ('1', 'LCP 30'), a dir name ('0001-two-sum'), or a URL."""
    token = token.strip().rstrip("/")
    m = re.search(r"leetcode\.(?:com|cn)/problems/([\w-]+)", token)
    if m:
        return m.group(1)
    ids = by_id()
    if token in ids or token.isdigit():
        p = ids.get(token) or ids.get(str(int(token))) if token.isdigit() else ids.get(token)
        if p:
            if not p.get("slug"):
                raise KeyError(f"{token} ({p.get('title')}) is a leetcode.cn-only problem; no slug on leetcode.com")
            return p["slug"]
        if SOLUTIONS_DIR.exists() and token.isdigit():
            for d in SOLUTIONS_DIR.iterdir():
                if d.name.startswith(f"{int(token):04d}-"):
                    return re.sub(r"^\d+-", "", d.name)
        catalog = PROBLEMS_DIR / "catalog.json"
        if token.isdigit() and catalog.exists():
            entry = json.loads(catalog.read_text()).get(token)
            if entry:
                return entry["slug"]
        raise KeyError(f"no problem with id {token} in the list, solutions/, or catalog")
    return re.sub(r"^\d{4}-", "", token)


def add_problem(entry: dict, name: Optional[str] = None) -> None:
    """Append a problem that is not in the list (custom pick) so progress can track it."""
    data = load_list(name)
    if any(p["slug"] == entry["slug"] for p in data["problems"] if p.get("slug")):
        return
    key = data["lists"][-1]["key"] if data["lists"] else "custom"
    entry = {"id": str(entry["id"]), "slug": entry["slug"], "title": entry.get("title"), "title_en": entry.get("title_en"),
             "difficulty": entry.get("difficulty"), "rating": None, "premium": False, "cn_only": False,
             "topic": entry.get("topic", "Custom"), "list": "custom", "section": "Custom picks", "note": "",
             "order": len(data["problems"]), "also_in": [], "custom": True}
    data["problems"].append(entry)
    custom = next((l for l in data["lists"] if l["key"] == "custom"), None)
    if not custom:
        custom = {"key": "custom", "name": "Custom picks", "url": "", "count": 0,
                  "sections": [{"path": "Custom picks", "ids": []}]}
        data["lists"].append(custom)
    custom["sections"][0]["ids"].append(entry["id"])
    custom["count"] = len(custom["sections"][0]["ids"])
    save_list(data, name)
