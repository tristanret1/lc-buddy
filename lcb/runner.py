"""Local test harness for Python solutions using tests.json + metaData."""
from __future__ import annotations

import importlib.util
import io
import json
import math
import signal
import sys
import time
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

from .config import ROOT
from .lctypes import from_lc, to_lc


class CaseTimeout(Exception):
    pass


def _alarm(_signum, _frame):
    raise CaseTimeout()


def load_module(path: Path):
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location(f"lcb_solution_{path.parent.name.replace('-', '_')}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def parse_expected(raw: Any) -> Any:
    if raw is None or not isinstance(raw, str):
        return raw
    s = raw.strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        low = s.lower()
        if low in ("true", "false"):
            return low == "true"
        if low in ("null", "none"):
            return None
        return s  # e.g. bare string without quotes


def canonical(v: Any) -> Any:
    if isinstance(v, float) and v.is_integer():
        return int(v)
    if isinstance(v, list):
        return [canonical(x) for x in v]
    return v


def _sorted_deep(v: Any) -> Any:
    if isinstance(v, list):
        items = [_sorted_deep(x) for x in v]
        try:
            return sorted(items, key=lambda x: json.dumps(x, sort_keys=True))
        except TypeError:
            return items
    return v


def equal(a: Any, b: Any, unordered: bool = False) -> tuple[bool, str]:
    a, b = canonical(a), canonical(b)
    if _eq(a, b):
        return True, ""
    if isinstance(a, list) and isinstance(b, list) and _eq(_sorted_deep(a), _sorted_deep(b)):
        return True, "order-insensitive match" if not unordered else ""
    return False, ""


def _eq(a: Any, b: Any) -> bool:
    if isinstance(a, float) or isinstance(b, float):
        try:
            return math.isclose(float(a), float(b), rel_tol=1e-5, abs_tol=1e-5)
        except (TypeError, ValueError):
            return False
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_eq(x, y) for x, y in zip(a, b))
    return a == b


def run_case(mod, meta: dict, inputs: list[str]) -> Any:
    md = meta["metaData"]
    args = [json.loads(line) for line in inputs]
    if md.get("systemdesign"):
        ops, arglists = args
        cls = getattr(mod, md["classname"])
        obj = cls(*arglists[0])
        out = [None]
        methods = {m["name"]: m for m in md["methods"]}
        for op, a in zip(ops[1:], arglists[1:]):
            ret = getattr(obj, op)(*a)
            out.append(None if methods.get(op, {}).get("return", {}).get("type") == "void" else to_lc(ret))
        return out
    params = md["params"]
    conv = [from_lc(v, p["type"]) for v, p in zip(args, params)]
    sol = mod.Solution()
    ret = getattr(sol, md["name"])(*conv)
    rtype = md.get("return", {}).get("type", "")
    if ret is None and rtype in ("ListNode", "TreeNode"):
        return []  # LeetCode prints an empty list for a null head/root
    if rtype == "void":
        # in-place problems print the first mutable argument
        for c in conv:
            if isinstance(c, list):
                return to_lc(c)
        return None
    return to_lc(ret)


def run_tests(sol_path: Path, meta: dict, tests: dict, only: int | None = None, timeout: int = 10) -> list[dict]:
    if not tests.get("local", True) or meta["metaData"].get("manual"):
        return [{"idx": 0, "skipped": True,
                 "reason": "problem uses a custom judge (manual=true); run `lcb test --remote` instead"}]
    if meta.get("lang") not in ("python3", "python"):
        return [{"idx": 0, "skipped": True, "reason": f"local harness only supports Python (lang={meta.get('lang')}); use --remote"}]
    mod = load_module(sol_path)
    unordered = tests.get("compare") == "unordered"
    results = []
    for i, case in enumerate(tests["cases"], 1):
        if only and i != only:
            continue
        r = {"idx": i, "input": case["input"], "expected": case.get("expected")}
        buf = io.StringIO()
        t0 = time.perf_counter()
        old = signal.signal(signal.SIGALRM, _alarm)
        signal.alarm(timeout)
        try:
            with redirect_stdout(buf):
                got = run_case(mod, meta, case["input"])
            r["got"] = json.dumps(got, separators=(",", ":"))
            exp = parse_expected(case.get("expected"))
            if case.get("expected") is None:
                r["status"], r["note"] = "unknown", "no expected value in tests.json"
            else:
                ok, note = equal(got, exp, unordered)
                r["status"], r["note"] = ("pass" if ok else "fail"), note
        except CaseTimeout:
            r["status"], r["note"] = "timeout", f">{timeout}s"
        except Exception as e:  # noqa: BLE001
            r["status"], r["note"] = "error", f"{type(e).__name__}: {e}"
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old)
        r["ms"] = round((time.perf_counter() - t0) * 1000, 1)
        r["stdout"] = buf.getvalue()
        results.append(r)
    return results


def format_results(results: list[dict]) -> str:
    lines = []
    for r in results:
        if r.get("skipped"):
            lines.append(f"  ~ skipped: {r['reason']}")
            continue
        icon = {"pass": "✅", "fail": "❌", "error": "💥", "timeout": "⏱", "unknown": "❔"}[r["status"]]
        lines.append(f"  {icon} case {r['idx']}  ({r['ms']} ms){'  ' + r['note'] if r.get('note') else ''}")
        if r["status"] != "pass":
            for j, line in enumerate(r["input"]):
                lines.append(f"       in[{j}]: {line[:200]}")
            lines.append(f"       expected: {str(r.get('expected'))[:200]}")
            if "got" in r:
                lines.append(f"       got:      {r['got'][:200]}")
        if r.get("stdout"):
            for out in r["stdout"].rstrip().splitlines()[:20]:
                lines.append(f"       > {out}")
    n_pass = sum(1 for r in results if r.get("status") == "pass")
    n_run = sum(1 for r in results if not r.get("skipped"))
    lines.append(f"  {n_pass}/{n_run} passed")
    return "\n".join(lines)


def all_passed(results: list[dict]) -> bool:
    ran = [r for r in results if not r.get("skipped")]
    return bool(ran) and all(r["status"] in ("pass",) for r in ran)
