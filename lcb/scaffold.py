"""Turn a LeetCode question payload into solutions/NNNN-slug/{solution.*, problem.md, tests.json, meta.json}."""
from __future__ import annotations

import html
import json
import re
from datetime import datetime
from pathlib import Path

from .config import LANG_EXT, SOLUTIONS_DIR
from .problems import dir_name

PY_HEADER = '''"""
{fid}. {title}  ({difficulty})
{url}
Topics: {topics}

Local harness: `python3 -m lcb test {slug}`   Submit: `python3 -m lcb submit {slug}`
"""
from typing import List, Optional, Dict, Set, Tuple, Deque  # lcb:strip
from collections import defaultdict, deque, Counter, OrderedDict  # lcb:strip
from heapq import heappush, heappop, heapify  # lcb:strip
import heapq, math, bisect, itertools, functools  # lcb:strip
from lcb.lctypes import ListNode, TreeNode, Node  # lcb:strip

'''

GENERIC_HEADER = '''// {fid}. {title}  ({difficulty})
// {url}
// Topics: {topics}

'''


# ---------- HTML -> Markdown (good enough for problem statements) ----------

def html_to_md(src: str) -> str:
    s = src
    pres = []

    def _pre(m):
        pres.append(_strip_tags(m.group(1)))
        return f"\n@@PRE{len(pres) - 1}@@\n"

    s = re.sub(r"<pre>(.*?)</pre>", _pre, s, flags=re.S)
    s = re.sub(r"<img[^>]*src=\"([^\"]+)\"[^>]*>", r"![](\1)", s)
    s = re.sub(r"<sup>(.*?)</sup>", r"^\1", s)
    s = re.sub(r"<(strong|b)>(.*?)</\1>", r"**\2**", s, flags=re.S)
    s = re.sub(r"<(em|i)>(.*?)</\1>", r"*\2*", s, flags=re.S)
    s = re.sub(r"<code>(.*?)</code>", r"`\1`", s, flags=re.S)
    s = re.sub(r"<li>(.*?)</li>", r"- \1\n", s, flags=re.S)
    s = re.sub(r"</?(ul|ol)>", "\n", s)
    s = re.sub(r"<p[^>]*>", "\n", s)
    s = re.sub(r"</p>", "\n", s)
    s = re.sub(r"<br\s*/?>", "\n", s)
    s = _strip_tags(s)
    for i, p in enumerate(pres):
        s = s.replace(f"@@PRE{i}@@", "```\n" + p.strip("\n") + "\n```")
    s = html.unescape(s).replace("\xa0", " ")
    s = re.sub(r"[ \t]+\n", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip() + "\n"


def _strip_tags(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", s))


# ---------- example extraction ----------

def parse_expected_outputs(content: str) -> list[str]:
    """Pull the 'Output' line of each <pre> example block, in order."""
    outs = []
    for block in re.findall(r"<pre>(.*?)</pre>", content, flags=re.S):
        text = _strip_tags(block)
        m = re.search(r"Output:?\s*\n?\s*(.+?)(?:\n|$)", text)
        if m and re.search(r"Input", text):
            outs.append(m.group(1).strip())
    return outs


def group_inputs(example_testcases: str, meta: dict) -> list[list[str]]:
    lines = [ln for ln in example_testcases.split("\n")]
    n = 2 if meta.get("systemdesign") else max(1, len(meta.get("params", [])))
    return [lines[i:i + n] for i in range(0, len(lines), n) if len(lines[i:i + n]) == n]


def build_tests(q: dict) -> dict:
    meta = q["metaData"]
    inputs = group_inputs(q.get("exampleTestcases") or q.get("sampleTestCase") or "", meta)
    expected = parse_expected_outputs(q.get("content") or "")
    cases = []
    for i, inp in enumerate(inputs):
        cases.append({"input": inp, "expected": expected[i] if i < len(expected) else None})
    return {
        "compare": "exact",   # or "unordered" when the problem says "return in any order"
        "local": not meta.get("manual", False),
        "cases": cases,
        "_help": "input = one string per parameter in LeetCode's format; expected = raw LeetCode output string. "
                 "Add your own cases freely. expected=null means 'unknown' (run `lcb test --remote` to see the judge's answer).",
    }


# ---------- files ----------

def snippet_for(q: dict, lang: str) -> str:
    for s in q.get("codeSnippets") or []:
        if s["langSlug"] == lang:
            return s["code"].rstrip() + "\n"
    raise ValueError(f"LeetCode has no {lang} template for {q['titleSlug']}")


def solution_source(q: dict, lang: str) -> str:
    fmt = dict(fid=q["questionFrontendId"], title=q["title"], difficulty=q["difficulty"],
               url=f"https://leetcode.com/problems/{q['titleSlug']}/", slug=q["titleSlug"],
               topics=", ".join(t["name"] for t in q.get("topicTags") or []) or "-")
    body = snippet_for(q, lang)
    if lang in ("python3", "python"):
        return PY_HEADER.format(**fmt) + _fill_empty_bodies(body) + "\n"
    return GENERIC_HEADER.format(**fmt) + body


def _fill_empty_bodies(code: str) -> str:
    """LeetCode's Python stubs leave method bodies empty (not importable). Insert `pass`."""
    lines = [ln.rstrip() for ln in code.splitlines()]
    out = []
    for i, ln in enumerate(lines):
        out.append(ln)
        if ln.strip().endswith(":") and not ln.lstrip().startswith("#"):
            indent = len(ln) - len(ln.lstrip())
            nxt = next((l for l in lines[i + 1:] if l.strip()), None)
            if nxt is None or (len(nxt) - len(nxt.lstrip())) <= indent:
                out.append(" " * (indent + 4) + "pass")
    return "\n".join(out).rstrip() + "\n"


def create(q: dict, lang: str, force: bool = False) -> Path:
    d = SOLUTIONS_DIR / dir_name(q["questionFrontendId"], q["titleSlug"])
    d.mkdir(parents=True, exist_ok=True)
    ext = LANG_EXT.get(lang, lang)
    sol = d / f"solution.{ext}"
    if sol.exists() and not force:
        raise FileExistsError(f"{sol} already exists (use --force to overwrite)")
    sol.write_text(solution_source(q, lang))
    (d / "problem.md").write_text(
        f"# {q['questionFrontendId']}. {q['title']}\n\n"
        f"**{q['difficulty']}** · https://leetcode.com/problems/{q['titleSlug']}/ · "
        f"Topics: {', '.join(t['name'] for t in q.get('topicTags') or []) or '-'}\n\n"
        + html_to_md(q.get("content") or "*(premium problem: statement not available)*")
        + ("\n\n## Hints\n" + "\n".join(f"{i + 1}. {html_to_md(h).strip()}" for i, h in enumerate(q["hints"]))
           if q.get("hints") else ""))
    tests = d / "tests.json"
    if not tests.exists() or force:
        tests.write_text(json.dumps(build_tests(q), indent=1) + "\n")
    (d / "meta.json").write_text(json.dumps({
        "id": int(q["questionFrontendId"]), "question_id": q["questionId"], "slug": q["titleSlug"],
        "title": q["title"], "difficulty": q["difficulty"], "lang": lang, "file": sol.name,
        "topics": [t["name"] for t in q.get("topicTags") or []], "metaData": q["metaData"],
        "created": datetime.now().isoformat(timespec="seconds"),
    }, indent=1) + "\n")
    return d


def strip_for_submit(code: str) -> str:
    """Remove local-only lines/blocks before sending to LeetCode."""
    out, skipping = [], False
    for line in code.splitlines():
        if "# lcb:begin-local" in line:
            skipping = True
            continue
        if "# lcb:end-local" in line:
            skipping = False
            continue
        if skipping or "# lcb:strip" in line:
            continue
        out.append(line)
    return "\n".join(out).strip() + "\n"
