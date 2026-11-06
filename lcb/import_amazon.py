"""Build problems/amazon.json from the company-wise CSVs in problems/amazon/.

Source: https://github.com/liquidslr/leetcode-company-wise-problems (Amazon/*.csv — LeetCode's
company tag exported by time window, with a 0-100 frequency score and the problem's topic tags).

Shape mirrors 0x3f.json so the rotation / focus / target-set machinery works unchanged:
  * lists[]  = one per topic bucket (array-hash, two-pointers, stack, ...), in a learning order
  * sections = frequency tiers inside each bucket: 近 30 天 → 近 3 个月 → 近 6 个月
  * problems ordered by frequency desc inside a section
Universe = the six-month window (~725 problems). Ratings come from 0x3f.json where the problem is
listed there; premium flags from catalog.json.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from .config import PROBLEMS_DIR

SRC_DIR = PROBLEMS_DIR / "amazon"
OUT = PROBLEMS_DIR / "amazon.json"
SOURCE_URL = "https://github.com/liquidslr/leetcode-company-wise-problems/tree/main/Amazon"

TIERS = [  # (csv file, section path)
    ("1. Thirty Days.csv", "§1 近 30 天高频"),
    ("2. Three Months.csv", "§2 近 3 个月"),
    ("3. Six Months.csv", "§3 近 6 个月"),
]

# bucket key -> (display name, tags that put a problem here). Order = rotation / reading order.
BUCKETS: list[tuple[str, str, set[str]]] = [
    ("array-hash",    "数组与哈希",       {"Array", "Hash Table", "Prefix Sum", "Sorting", "Matrix", "Simulation", "Counting", "Enumeration"}),
    ("two-pointers",  "双指针与滑动窗口",  {"Two Pointers", "Sliding Window"}),
    ("stack",         "栈与单调栈",       {"Stack", "Monotonic Stack", "Monotonic Queue", "Queue"}),
    ("binary-search", "二分",            {"Binary Search"}),
    ("linked-list",   "链表",            {"Linked List", "Doubly-Linked List"}),
    ("tree",          "树",              {"Tree", "Binary Tree", "Binary Search Tree", "Trie", "Segment Tree", "Binary Indexed Tree"}),
    ("graph",         "图与网格 (BFS/DFS)", {"Graph", "Breadth-First Search", "Depth-First Search", "Union Find", "Topological Sort", "Shortest Path", "Minimum Spanning Tree"}),
    ("heap",          "堆与 Top-K",       {"Heap (Priority Queue)", "Ordered Set", "Bucket Sort", "Quickselect", "Divide and Conquer"}),
    ("backtracking",  "回溯",            {"Backtracking", "Recursion"}),
    ("dp",            "动态规划",         {"Dynamic Programming", "Memoization"}),
    ("design",        "设计题",           {"Design", "Iterator", "Data Stream"}),
    ("greedy",        "贪心与区间",        {"Greedy", "Interval", "Line Sweep"}),
    ("string",        "字符串",           {"String", "String Matching", "Rolling Hash", "Hash Function"}),
    ("math-bit",      "数学与位运算",      {"Math", "Bit Manipulation", "Number Theory", "Geometry", "Combinatorics", "Game Theory", "Randomized", "Rejection Sampling", "Probability and Statistics"}),
]
# Tags that decide the bucket on their own, checked in this priority order (Design beats Linked List
# for LRU Cache; Topological Sort beats DFS for Course Schedule; ...).
OVERRIDE: list[tuple[str, str]] = [
    ("Design", "design"), ("Trie", "tree"), ("Backtracking", "backtracking"),
    ("Topological Sort", "graph"), ("Union Find", "graph"), ("Sliding Window", "two-pointers"),
    ("Monotonic Stack", "stack"), ("Heap (Priority Queue)", "heap"), ("Linked List", "linked-list"),
]
GENERIC = {"Array", "String", "Hash Table", "Sorting", "Matrix", "Simulation", "Math", "Counting", "Enumeration"}


def _bucket(tags: list[str]) -> str:
    tagset = set(tags)
    for t, key in OVERRIDE:
        if t in tagset:
            return key
    for t in tags:  # first specific tag in LeetCode's own order
        if t in GENERIC:
            continue
        for key, _, members in BUCKETS:
            if t in members:
                return key
    for t in tags:  # only generic tags left
        for key, _, members in BUCKETS:
            if t in members:
                return key
    return "array-hash"


def _read(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main() -> int:
    for f, _ in TIERS:
        if not (SRC_DIR / f).exists():
            print(f"missing {SRC_DIR / f}")
            return 1
    catalog = json.loads((PROBLEMS_DIR / "catalog.json").read_text(encoding="utf-8"))
    slug2id = {v["slug"]: (k, v) for k, v in catalog.items()}
    x3f_path = PROBLEMS_DIR / "0x3f.json"
    x3f = {}
    if x3f_path.exists():
        x3f = {p["slug"]: p for p in json.loads(x3f_path.read_text(encoding="utf-8"))["problems"] if p.get("slug")}

    tier_of: dict[str, str] = {}
    rows: dict[str, dict] = {}
    for f, section in TIERS:
        for r in _read(SRC_DIR / f):
            slug = r["Link"].rstrip("/").split("/")[-1]
            tier_of.setdefault(slug, section)       # earliest (hottest) tier wins
            rows.setdefault(slug, r)                 # keep the row from the hottest tier (its frequency)
    missing = [s for s in rows if s not in slug2id]
    if missing:
        print(f"warning: {len(missing)} slugs not in catalog.json (run `lcb catalog`): {missing[:5]}")

    names = {k: n for k, n, _ in BUCKETS}
    problems: list[dict] = []
    per_list: dict[str, dict[str, list]] = {k: {sec: [] for _, sec in TIERS} for k, _, _ in BUCKETS}
    for slug, r in rows.items():
        if slug not in slug2id:
            continue
        pid, cat = slug2id[slug]
        tags = [t.strip() for t in r["Topics"].split(",") if t.strip()]
        key = _bucket(tags)
        freq = float(r["Frequency"] or 0)
        x = x3f.get(slug, {})
        problems.append({
            "id": str(pid), "slug": slug,
            "title": x.get("title") or cat["title"], "title_en": cat["title"],
            "difficulty": r["Difficulty"].capitalize(),
            "rating": x.get("rating"), "rating_approx": x.get("rating_approx", False),
            "premium": bool(cat.get("premium")), "cn_only": False,
            "topic": names[key], "list": key, "section": tier_of[slug],
            "note": "", "order": 0, "also_in": [],
            "frequency": freq, "tags": tags,
        })
        per_list[key][tier_of[slug]].append((freq, str(pid)))

    lists = []
    order = 0
    by_id = {p["id"]: p for p in problems}
    for key, name, _ in BUCKETS:
        sections = []
        for _, sec in TIERS:
            ids = [pid for _, pid in sorted(per_list[key][sec], key=lambda t: -t[0])]
            if not ids:
                continue
            for pid in ids:
                by_id[pid]["order"] = order
                order += 1
            sections.append({"path": sec, "ids": ids})
        lists.append({"key": key, "name": name, "url": SOURCE_URL,
                      "count": sum(len(s["ids"]) for s in sections), "sections": sections})
    problems.sort(key=lambda p: p["order"])

    out = {
        "name": "Amazon 高频题单",
        "kind": "hierarchical",
        "source": SOURCE_URL,
        "description": "LeetCode Amazon company tag, six-month window, grouped by topic and frequency tier "
                       "(近 30 天 → 近 3 个月 → 近 6 个月), frequency-desc inside a tier.",
        "lists": lists,
        "problems": problems,
    }
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    prem = sum(p["premium"] for p in problems)
    print(f"wrote {OUT.relative_to(PROBLEMS_DIR.parent)}: {len(problems)} problems ({prem} premium), {len(lists)} lists")
    for L in lists:
        print(f"  {L['key']:<14} {L['name']:<16} {L['count']:>4}   " + "  ".join(f"{s['path']} {len(s['ids'])}" for s in L["sections"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
