"""Paths and user config. Everything lives relative to the repo root."""
from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOLUTIONS_DIR = ROOT / "solutions"
PROBLEMS_DIR = ROOT / "problems"
PROGRESS_FILE = ROOT / "progress.json"
CONFIG_FILE = ROOT / "config.json"
README_FILE = ROOT / "PROGRESS.md"   # the auto-generated dashboard (README.md is the project docs)
AUTH_FILE = Path(os.environ.get("LCB_AUTH_FILE", Path.home() / ".config" / "lc_buddy" / "auth.json"))

DEFAULT_CONFIG = {
    "lang": "python3",           # LeetCode langSlug used for scaffolding + submission
    "list": "0x3f",              # problems/<list>.json  (0x3f = 灵茶山艾府题单, grind75 also available)
    "daily_new": 1,              # new problems per day the plan assumes
    "review_intervals": [3, 7, 14, 30],  # spaced-repetition ladder in days
    "target_date": None,         # optional "YYYY-MM-DD" interview date
    "git_commit": True,          # commit after each submission
    "git_push": True,            # and push to the remote if one is configured
    "auth_browser": None,        # "chrome"/"arc"/"brave"/"edge"/"chromium": re-read LeetCode cookies from it when they expire
    # --- target-set filters (what "the plan" expects you to solve) ---
    "max_rating": 2200,          # skip problems whose 难度分 is above this (None = no cap)
    "skip_premium": True,        # skip 会员题
    "skip_optional": True,       # skip 0x3f sections marked 选做 (optional); they stay listed but leave the target set
    "focus": [],                 # list keys ("dp") or section prefixes ("dp / 三、背包") to grind first; [] = whole list in order
    "goal": None,                # solved count that means "plan done" (None = whole list if ≤150, else 300)
    # --- daily scheduler: category rotation + forgetting curve ---
    "rotation": {
        "enabled": True,         # rotate through the lists: solve `block` new problems in one list, then move on
        "block": 5,              # new problems per list per cycle
        "order": [],             # list keys in rotation order; [] = focus order if focus set, else 题单 order
    },
    "daily_reviews": 2,          # max review items per day (错题 first, then 旧题); overflow waits
    "weak_interval": 1,          # days until re-check for 错题 (accepted only after failures / stumbled review / confidence ≤ 2)
}

LANG_EXT = {
    "python3": "py", "python": "py", "cpp": "cpp", "java": "java", "javascript": "js",
    "typescript": "ts", "golang": "go", "rust": "rs", "kotlin": "kt", "swift": "swift",
    "csharp": "cs", "c": "c", "ruby": "rb", "scala": "scala", "php": "php", "dart": "dart",
}


def load_config() -> dict:
    cfg = dict(DEFAULT_CONFIG)
    if CONFIG_FILE.exists():
        cfg.update(json.loads(CONFIG_FILE.read_text()))
    return cfg


def save_config(cfg: dict) -> None:
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2) + "\n")
