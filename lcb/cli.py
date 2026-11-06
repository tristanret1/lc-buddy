"""`python3 -m lcb <command>` — the entry point the skills call."""
from __future__ import annotations

import argparse
import json
import sys
import webbrowser
from pathlib import Path

from . import design, gitops, jobs, leetcode, progress, readme, scaffold
from .config import LANG_EXT, PROGRESS_FILE, README_FILE, SOLUTIONS_DIR, load_config, save_config
from .problems import add_problem, by_slug, in_target, load_list, ordered, problems, resolve_slug, solution_dir, target_problems
from .runner import all_passed, format_results, run_tests


def _die(msg: str, code: int = 1) -> int:
    print(f"error: {msg}", file=sys.stderr)
    return code


def _load_solution(slug: str) -> tuple[Path, dict, Path, dict]:
    d = solution_dir(slug)
    if not d:
        raise FileNotFoundError(f"no solutions/ directory for {slug!r}. Run `lcb new {slug}` first.")
    meta = json.loads((d / "meta.json").read_text())
    sol = d / meta["file"]
    tests = json.loads((d / "tests.json").read_text()) if (d / "tests.json").exists() else {"cases": []}
    return d, meta, sol, tests


def _print_problem_header(p: dict, d: Path) -> None:
    print(f"\n{p['id']}. {p['title']}  [{p['difficulty']}]  {', '.join(p.get('topics') or [])}")
    print(f"  dir:       {d.relative_to(d.parent.parent)}")
    print(f"  statement: {d.name}/problem.md")
    print(f"  code:      {d.name}/{p['file']}")
    print(f"  url:       https://leetcode.com/problems/{p['slug']}/")


# ---------- commands ----------

def _ptitle(p: dict) -> str:
    t = p.get("title") or p.get("title_en") or p.get("slug") or ""
    r = f", {p['rating']}" if p.get("rating") else ""
    return f"{t}  ({p.get('difficulty') or '?'}{r})"


def cmd_next(a) -> int:
    data = progress.load()
    cfg = load_config()
    if getattr(a, "list_key", None) or getattr(a, "section", None):
        picks = progress.next_new(data, a.count or cfg["daily_new"], list_key=a.list_key, section=a.section)
        if a.json:
            print(json.dumps(picks, ensure_ascii=False, indent=1))
            return 0
        print("Next new" + (f" in {a.list_key}" if a.list_key else "") + (f" / {a.section}" if a.section else "") + ":")
        for p in picks:
            print(f"  ⬜ {p['id']:>5}  {_ptitle(p)}  {p['slug']}")
            print(f"           {p['topic']} / {p['section']}" + (f"   · {p['note']}" if p.get('note') else ""))
        return 0
    pl = progress.plan(data, a.count)
    if a.json:
        print(json.dumps(pl, ensure_ascii=False, indent=1, default=str))
        return 0
    rot = pl["rotation"]
    if rot and rot["current"]:
        print(f"Today's category: {rot['current_name']} ({rot['current']})  —  block {rot['in_block']}/{rot['block']}, cycle {rot['cycle']}"
              + (f"  →  next: {rot['next_name']}" if rot.get("next") else ""))
    elif rot:
        print("Rotation complete — every list's target set is solved. 🎉")
    if pl["new"]:
        print("1. 新题:")
        for p in pl["new"]:
            print(f"  ⬜ {p['id']:>5}  {_ptitle(p)}  {p['slug']}")
            print(f"           {p['topic']} / {p['section']}" + (f"   · {p['note']}" if p.get('note') else ""))
    if pl["unfinished"]:
        print("   未通关 (attempted, not accepted):")
        for p in pl["unfinished"]:
            print(f"  🔧 {p['id']:>5}  {_ptitle(p)}  {p['attempts']} attempt(s)  {p['slug']}")
    elif pl["in_progress"]:
        print("   进行中 (scaffolded, not submitted):")
        for p in pl["in_progress"]:
            print(f"  🔧 {p['id']:>5}  {_ptitle(p)}  {p['slug']}")
    if pl["weak"]:
        print("2. 错题 (weak, due):")
        for p in pl["weak"]:
            print(f"  🔁 {p['id']:>5}  {_ptitle(p)}  box {p['box']}, due {p['next_review']}  →  lcb review {p['slug']}")
    if pl["old"]:
        print("3. 旧题 (review due):")
        for p in pl["old"]:
            print(f"  🔁 {p['id']:>5}  {_ptitle(p)}  box {p['box']}, due {p['next_review']}  →  lcb review {p['slug']}")
    if pl["deferred"]:
        print(f"   (+{pl['deferred']} more reviews due; capped at daily_reviews={cfg.get('daily_reviews', 2)})")
    if not (pl["new"] or pl["weak"] or pl["old"] or pl["unfinished"] or pl["in_progress"]):
        print("Nothing pending — target set complete and no reviews due. 🎉 (widen focus/max_rating in config.json)")
    return 0


def cmd_new(a) -> int:
    cfg = load_config()
    lang = a.lang or cfg["lang"]
    if a.slug:
        try:
            slug = resolve_slug(a.slug)
        except KeyError as e:
            return _die(str(e))
    else:
        if a.list_key or a.section:
            picks = progress.next_new(n=1, list_key=a.list_key, section=a.section)
        else:
            picks = progress.plan(n_new=1)["new"]
        if not picks:
            print("No new problems left in the target set (check focus / max_rating / --list).")
            return 0
        slug = picks[0]["slug"]
    existing = solution_dir(slug)
    if existing and not a.force:
        meta = json.loads((existing / "meta.json").read_text())
        _print_problem_header(meta, existing)
        print("  (already scaffolded — nothing changed)")
        return 0
    try:
        q = leetcode.fetch_question(slug)
    except leetcode.LeetCodeError as e:
        return _die(str(e))
    if q.get("isPaidOnly"):
        print("warning: premium problem; statement/tests may be missing.", file=sys.stderr)
    try:
        d = scaffold.create(q, lang, force=a.force)
    except (FileExistsError, ValueError) as e:
        return _die(str(e))
    if slug not in by_slug():
        add_problem({"id": q["questionFrontendId"], "slug": slug, "difficulty": q["difficulty"], "title_en": q["title"],
                     "topic": (q.get("topicTags") or [{"name": "Misc"}])[0]["name"]})
    progress.record_new(slug)
    readme.write()
    meta = json.loads((d / "meta.json").read_text())
    _print_problem_header(meta, d)
    n = len(json.loads((d / "tests.json").read_text())["cases"])
    print(f"  tests:     {n} example case(s) in tests.json")
    if a.open:
        webbrowser.open(f"https://leetcode.com/problems/{slug}/")
    return 0


def cmd_test(a) -> int:
    slug = resolve_slug(a.slug) if a.slug else _guess_current()
    try:
        d, meta, sol, tests = _load_solution(slug)
    except FileNotFoundError as e:
        return _die(str(e))
    print(f"{meta['id']}. {meta['title']}  —  {sol.relative_to(sol.parent.parent.parent)}")
    if a.remote:
        return _remote_run(meta, sol, tests, a.case)
    results = run_tests(sol, meta, tests, only=a.case, timeout=a.timeout)
    print(format_results(results))
    if a.json:
        print(json.dumps(results, indent=1))
    return 0 if all_passed(results) else 1


def _remote_run(meta: dict, sol: Path, tests: dict, only: int | None) -> int:
    code = scaffold.strip_for_submit(sol.read_text())
    cases = tests.get("cases") or []
    if only:
        cases = [cases[only - 1]]
    if not cases:
        return _die("no cases in tests.json")
    data_input = "\n".join(line for c in cases for line in c["input"])
    try:
        res = leetcode.run_code(meta["slug"], meta["question_id"], meta["lang"], code, data_input)
    except leetcode.LeetCodeError as e:
        return _die(str(e))
    ok = True
    if not res.get("run_success", True):
        print(f"  💥 {res.get('status_msg')}")
        print("  " + (res.get("full_runtime_error") or res.get("runtime_error") or res.get("compile_error") or "")[:800])
        return 1
    got, exp = res.get("code_answer") or [], res.get("expected_code_answer") or []
    for i, (g, e) in enumerate(zip(got, exp), 1):
        same = _lenient_eq(g, e)
        ok &= same
        print(f"  {'✅' if same else '❌'} case {i}   got: {g[:120]}   expected: {e[:120]}")
    for c, e in zip(cases, exp):  # backfill unknown expected values
        if c.get("expected") is None:
            c["expected"] = e
    if any(c.get("expected") is not None for c in cases):
        (sol.parent / "tests.json").write_text(json.dumps(tests, indent=1) + "\n")
    print(f"  judge: {res.get('status_msg')}  runtime {res.get('status_runtime')}  memory {res.get('status_memory')}")
    for line in (res.get("std_output_list") or []):
        if line.strip():
            print("  > " + line.strip()[:300])
    return 0 if ok else 1


def _lenient_eq(a: str, b: str) -> bool:
    from .runner import equal, parse_expected
    return equal(parse_expected(a), parse_expected(b))[0]


def cmd_submit(a) -> int:
    cfg = load_config()
    slug = resolve_slug(a.slug) if a.slug else _guess_current()
    try:
        d, meta, sol, tests = _load_solution(slug)
    except FileNotFoundError as e:
        return _die(str(e))
    print(f"{meta['id']}. {meta['title']}  —  submitting {sol.name} ({meta['lang']})")
    if not a.skip_local and meta["lang"] in ("python3", "python"):
        results = run_tests(sol, meta, tests)
        skipped = all(r.get("skipped") for r in results)
        if not skipped:
            print(format_results(results))
            if not all_passed(results) and not a.force:
                return _die("local tests not green; fix them or pass --force to submit anyway")
    code = scaffold.strip_for_submit(sol.read_text())
    try:
        res = leetcode.submit_code(meta["slug"], meta["question_id"], meta["lang"], code)
    except leetcode.LeetCodeError as e:
        return _die(str(e))
    status = res.get("status_msg", "Unknown")
    norm = {
        "status": status, "id": res.get("submission_id"), "url": res.get("submission_url"),
        "runtime": res.get("status_runtime"), "memory": res.get("status_memory"),
        "runtime_pct": _round(res.get("runtime_percentile")), "memory_pct": _round(res.get("memory_percentile")),
        "passed": f"{res.get('total_correct')}/{res.get('total_testcases')}",
    }
    e = progress.record_submission(slug, norm)
    accepted = status == "Accepted"
    if accepted:
        print(f"\n  ✅ Accepted  runtime {norm['runtime']} (beats {norm['runtime_pct']}%)  memory {norm['memory']} (beats {norm['memory_pct']}%)")
        print(f"  attempts: {e['attempts']}   status: {e['status']}   next review: {e['srs'].get('next_review') or '—'}")
    else:
        print(f"\n  ❌ {status}  ({norm['passed']} testcases)")
        for k in ("last_testcase", "expected_output", "code_output"):
            if res.get(k):
                print(f"  {k.replace('_', ' ')}: {str(res[k])[:300]}")
        err = res.get("full_compile_error") or res.get("full_runtime_error") or res.get("compile_error") or res.get("runtime_error")
        if err:
            print("  " + err[:800])
    print(f"  {norm['url']}")
    readme.write()
    print("  PROGRESS.md regenerated")
    if cfg.get("git_commit", True) and not a.no_commit:
        msg = a.message or f"{'solve' if accepted else 'attempt'}({meta['id']}): {meta['title']} — {status}"
        try:
            sha = gitops.commit([d, PROGRESS_FILE, README_FILE, Path("problems"), Path("docs")], msg)
            print(f"  committed {sha}: {msg}" if sha else "  nothing new to commit")
            if sha and cfg.get("git_push", True):
                status = gitops.push()
                if status:
                    print(f"  {status}")
        except RuntimeError as err:
            print(f"  git commit failed: {err}", file=sys.stderr)
    return 0 if accepted else 2


def _round(v):
    try:
        return round(float(v), 1)
    except (TypeError, ValueError):
        return None


def cmd_review(a) -> int:
    slug = resolve_slug(a.slug)
    try:
        d, meta, sol, tests = _load_solution(slug)
    except FileNotFoundError as e:
        return _die(str(e))
    attempts = d / "attempts"
    attempts.mkdir(exist_ok=True)
    from datetime import date
    archived = attempts / f"{date.today().isoformat()}.{LANG_EXT.get(meta['lang'], 'txt')}"
    archived.write_text(sol.read_text())
    q = leetcode.fetch_question(slug)
    sol.write_text(scaffold.solution_source(q, meta["lang"]))
    progress.start_review(slug)
    readme.write()
    print(f"{meta['id']}. {meta['title']} — review started.")
    print(f"  previous solution archived to {archived.relative_to(d.parent.parent)}")
    print(f"  {sol.relative_to(d.parent.parent)} reset to a blank stub. Solve from scratch, then `lcb submit {slug}`.")
    return 0


def cmd_skip(a) -> int:
    slug = resolve_slug(a.slug)
    try:
        e = progress.skip_review(slug)
    except KeyError as err:
        return _die(str(err))
    if a.confidence:
        progress.set_confidence(slug, a.confidence)
    readme.write()
    nxt = e["srs"]["next_review"]
    print(f"{slug}: review skipped as a clean pass → box {e['srs']['box']}, "
          + (f"next review {nxt}" if nxt else "mastered 🏆"))
    return 0


def cmd_status(a) -> int:
    s = progress.stats()
    if a.json:
        print(json.dumps(s, indent=1, default=str))
        return 0
    print(f"{s['list_name']}: target {s['total']} of {s['total_all']} listed, goal {s['goal']}"
          + (f", focus {s['focus']}" if s['focus'] else ""))
    print(f"Readiness {s['readiness']}/100   {readme.bar(s['readiness'] / 100)}   {readme.verdict(s['readiness'])}")
    print(f"Solved {s['solved']}/{s['goal']} toward goal ({s['solved_all']} total; mastered {s['mastered']}, "
          f"in progress {s['in_progress']}, reviews due {s['review_due']}, streak {s['streak']}d)")
    for dname, v in s["by_difficulty"].items():
        print(f"  {dname:<7} {v['solved']:>3}/{v['total']:<3} {readme.bar(v['solved'] / v['total'] if v['total'] else 0, 12)}")
    print(f"Pace: {s['recent_14d']} solved in 14d ({s['actual_pace']:.2f}/day); plan {s['planned_pace']:.0f}/day; {s['remaining']} remaining")
    if s["remaining"]:
        print(f"ETA: planned {s['eta_planned']}" + (f" · actual {s['eta_actual']}" if s["eta_actual"] else ""))
    if s.get("target_date"):
        print(f"Target date: {s['target_date']}")
    lists = [(k, v) for k, v in s["by_list"].items() if v["target"]]
    weak = sorted(lists, key=lambda kv: kv[1]["solved"] / kv[1]["target"])[:4]
    print("Weakest lists: " + ", ".join(f"{v['name']} {v['solved']}/{v['target']}" for k, v in weak))
    print()
    return cmd_next(argparse.Namespace(count=None, json=False, list_key=None, section=None))


def cmd_readme(a) -> int:
    readme.write()
    print(f"wrote {README_FILE.relative_to(README_FILE.parent)}")
    return 0


def cmd_list(a) -> int:
    data = progress.load()
    cfg = load_config()
    n = 0
    for p in ordered(a.list_key, a.section):
        tgt = in_target(p, cfg, ignore_focus=True)
        if a.target and not tgt:
            continue
        st = progress.status_of(data, p.get("slug"))
        if a.filter and st != a.filter:
            continue
        flags = ("会员 " if p.get("premium") else "") + ("cn " if p.get("cn_only") else "") + ("" if tgt else "skip ")
        rating = f"{p['rating']}{'≈' if p.get('rating_approx') else ''}" if p.get("rating") else ""
        print(f"{readme.ICON[st]} {p['id']:>6}  {(p.get('title') or p.get('title_en') or ''):<32} {p.get('difficulty') or '':<7} "
              f"{rating:<6} {flags:<8} {p['list']} / {p['section']}")
        n += 1
    print(f"{n} problems")
    return 0


def cmd_lists(a) -> int:
    s = progress.stats()
    rot = progress.rotation_state()
    marks = {r["key"]: r for r in rot["lists"]}
    print(f"{s['list_name']}  —  {s['total_all']} listed, {s['total']} in target, goal {s['goal']}; "
          f"rotation block {rot['block']}, cycle {rot['cycle']}")
    for key, v in s["by_list"].items():
        r = marks.get(key)
        tag = "▶" if r and r.get("current") else " "
        blk = f"block {r['in_block']}/{rot['block']}" if r else "not in rotation"
        print(f"{tag} {key:<32} {v['name']:<12} solved {v['solved']:>4} / target {v['target']:>4} / listed {v['total']:>4}"
              f"   {readme.bar(v['solved'] / v['target'] if v['target'] else 0, 16)}  {blk}")
    if a.sections:
        for key, v in s["by_list"].items():
            if a.sections not in (key, "all"):
                continue
            print(f"\n{v['name']}")
            for sec, sv in v["sections"].items():
                print(f"    {sv['solved']:>3}/{sv['target']:<3} {readme.bar(sv['solved'] / sv['target'] if sv['target'] else 0, 10)}  {sec}")
    return 0


def cmd_catalog(a) -> int:
    import urllib.request
    req = urllib.request.Request("https://leetcode.com/api/problems/all/", headers={"User-Agent": leetcode.UA})
    d = json.load(urllib.request.urlopen(req, timeout=60))
    cat = {}
    for p in d["stat_status_pairs"]:
        st = p["stat"]
        cat[str(st["frontend_question_id"])] = {"slug": st["question__title_slug"], "title": st["question__title"],
            "difficulty": {1: "Easy", 2: "Medium", 3: "Hard"}[p["difficulty"]["level"]], "paid_only": None,
            "premium": bool(p["paid_only"])}
        cat[str(st["frontend_question_id"])].pop("paid_only")
    out = Path("problems/catalog.json")
    out.write_text(json.dumps(cat, ensure_ascii=False, indent=0, sort_keys=True))
    print(f"wrote {out} with {len(cat)} problems")
    return 0


def cmd_import(a) -> int:
    if a.source == "amazon":
        from . import import_amazon
        rc = import_amazon.main()
    else:
        from . import import_0x3f
        rc = import_0x3f.main()
    readme.write()
    return rc


def cmd_note(a) -> int:
    slug = resolve_slug(a.slug)
    progress.set_note(slug, " ".join(a.text))
    readme.write()
    return 0


def cmd_confidence(a) -> int:
    progress.set_confidence(resolve_slug(a.slug), a.level)
    readme.write()
    return 0


def cmd_auth(a) -> int:
    if a.from_browser:
        try:
            leetcode.refresh_auth_from_browser(a.from_browser, a.profile)
        except leetcode.LeetCodeError as e:
            return _die(str(e))
        print(f"cookies read from {a.from_browser} → {leetcode.AUTH_FILE}")
        cfg = load_config()
        if cfg.get("auth_browser") != a.from_browser:
            cfg["auth_browser"] = a.from_browser
            save_config(cfg)
            print(f"config: auth_browser = {a.from_browser!r} (expired cookies now auto-refresh from it)")
    elif a.session and a.csrf:
        leetcode.save_auth(a.session, a.csrf)
        print(f"saved to {leetcode.AUTH_FILE}")
    try:
        u = leetcode.whoami()
    except leetcode.LeetCodeError as e:
        print(str(e), file=sys.stderr)
        print("\nEasiest: log in at leetcode.com in Chrome, then  python3 -m lcb auth --from-browser chrome\n"
              "  (also: arc, brave, edge, chromium; --profile 'Profile 1' for a non-default profile)\n"
              "Manual: DevTools → Application → Cookies → copy  LEETCODE_SESSION  and  csrftoken, then\n"
              "  python3 -m lcb auth --session <LEETCODE_SESSION> --csrf <csrftoken>\n"
              "(or export LEETCODE_SESSION / LEETCODE_CSRF in your shell)", file=sys.stderr)
        return 1
    print(f"signed in as {u.get('username')}")
    return 0


def cmd_config(a) -> int:
    cfg = load_config()
    if a.set:
        for kv in a.set:
            k, _, v = kv.partition("=")
            try:
                cfg[k] = json.loads(v)
            except json.JSONDecodeError:
                cfg[k] = v
        save_config(cfg)
    print(json.dumps(cfg, indent=2))
    return 0


def cmd_open(a) -> int:
    slug = resolve_slug(a.slug) if a.slug else _guess_current()
    webbrowser.open(f"https://leetcode.com/problems/{slug}/")
    return 0


def _guess_current() -> str:
    """No slug given: the single in-progress problem, else the most recently scaffolded dir."""
    wip = progress.in_progress()
    if len(wip) == 1:
        return wip[0]["slug"]
    dirs = sorted((d for d in SOLUTIONS_DIR.glob("*/") if (d / "meta.json").exists()),
                  key=lambda d: (d / "meta.json").stat().st_mtime, reverse=True)
    if dirs:
        return json.loads((dirs[0] / "meta.json").read_text())["slug"]
    raise SystemExit(_die("no problem given and none in progress"))


# ---------- parser ----------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="lcb", description="LeetCode grind companion")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("next", help="what to work on today (reviews due + next new)")
    s.add_argument("-n", "--count", type=int)
    s.add_argument("--list", dest="list_key", help="restrict the new pick to a list key (e.g. dp)")
    s.add_argument("--section", help="restrict the new pick to a section prefix (e.g. '三、背包')")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_next)

    s = sub.add_parser("new", help="scaffold a problem (default: next unsolved in the target set)")
    s.add_argument("slug", nargs="?", help="slug, id, or URL")
    s.add_argument("--list", dest="list_key", help="pick the next problem from this list key")
    s.add_argument("--section", help="pick the next problem from this section prefix")
    s.add_argument("--lang")
    s.add_argument("--force", action="store_true", help="overwrite existing stub")
    s.add_argument("--open", action="store_true", help="open in browser")
    s.set_defaults(fn=cmd_new)

    s = sub.add_parser("test", help="run tests.json locally (or --remote on LeetCode)")
    s.add_argument("slug", nargs="?")
    s.add_argument("--remote", action="store_true")
    s.add_argument("--case", type=int, help="run only case N (1-based)")
    s.add_argument("--timeout", type=int, default=10)
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_test)

    s = sub.add_parser("submit", help="submit to LeetCode, record verdict, regenerate PROGRESS.md, commit")
    s.add_argument("slug", nargs="?")
    s.add_argument("--force", action="store_true", help="submit even if local tests fail")
    s.add_argument("--skip-local", action="store_true")
    s.add_argument("--no-commit", action="store_true")
    s.add_argument("-m", "--message")
    s.set_defaults(fn=cmd_submit)

    s = sub.add_parser("review", help="archive current solution and re-solve from scratch (spaced repetition)")
    s.add_argument("slug")
    s.set_defaults(fn=cmd_review)

    s = sub.add_parser("skip", help="skip a due review as a clean pass (you know it cold): climbs one box")
    s.add_argument("slug")
    s.add_argument("--confidence", type=int, choices=range(1, 6), help="also record self-rated confidence 1-5")
    s.set_defaults(fn=cmd_skip)

    s = sub.add_parser("status", help="readiness summary")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_status)

    sub.add_parser("readme", help="regenerate PROGRESS.md (dashboard) and docs/").set_defaults(fn=cmd_readme)

    s = sub.add_parser("list", help="list problems with status")
    s.add_argument("--filter", choices=["todo", "in_progress", "solved", "review_due", "mastered"])
    s.add_argument("--list", dest="list_key", help="only this list key")
    s.add_argument("--section", help="only sections starting with this prefix")
    s.add_argument("--target", action="store_true", help="only problems in the target set")
    s.set_defaults(fn=cmd_list)

    s = sub.add_parser("lists", help="show the lists (topics) and per-list progress")
    s.add_argument("--sections", metavar="KEY|all", help="also show per-section progress for one list key or all")
    s.set_defaults(fn=cmd_lists)

    sub.add_parser("catalog", help="refresh problems/catalog.json from leetcode.com (id → slug/difficulty/premium)").set_defaults(fn=cmd_catalog)
    s = sub.add_parser("import", help="rebuild a problem list from its sources (0x3f: problems/0x3f/*.txt; amazon: problems/amazon/*.csv) and regenerate PROGRESS.md")
    s.add_argument("--source", choices=["0x3f", "amazon"], default="0x3f")
    s.set_defaults(fn=cmd_import)

    s = sub.add_parser("note", help="attach a note to a problem")
    s.add_argument("slug")
    s.add_argument("text", nargs="+")
    s.set_defaults(fn=cmd_note)

    s = sub.add_parser("confidence", help="record self-rated confidence 1-5")
    s.add_argument("slug")
    s.add_argument("level", type=int)
    s.set_defaults(fn=cmd_confidence)

    s = sub.add_parser("auth", help="store LeetCode cookies / check login")
    s.add_argument("--from-browser", nargs="?", const="chrome", metavar="BROWSER",
                   help="read LEETCODE_SESSION + csrftoken from a local browser (chrome, arc, brave, edge, chromium) "
                        "and remember it in config so expired cookies auto-refresh")
    s.add_argument("--profile", help="browser profile dir name, e.g. 'Profile 1' (default: Default, then others)")
    s.add_argument("--session")
    s.add_argument("--csrf")
    s.set_defaults(fn=cmd_auth)

    s = sub.add_parser("config", help="show or set config (e.g. --set lang=golang --set daily_new=2)")
    s.add_argument("--set", action="append")
    s.set_defaults(fn=cmd_config)

    s = sub.add_parser("jobs", help="job pipeline: board / add / set / note / show / rm / profile")
    js = s.add_subparsers(dest="jobs_cmd")
    s.add_argument("--all", action="store_true", help="include closed (offer/rejected/withdrawn/stale)")
    s.set_defaults(fn=cmd_jobs)
    j = js.add_parser("board", help="pipeline board (default)")
    j.add_argument("--all", action="store_true")
    j = js.add_parser("add", help="track a role")
    j.add_argument("--company", required=True)
    j.add_argument("--title", required=True)
    for opt in ("url", "location", "remote", "salary", "level", "source", "fit_notes", "interview_format", "next_action", "next_date", "note"):
        j.add_argument(f"--{opt.replace('_', '-')}", dest=opt)
    j.add_argument("--prep", help="semicolon-separated prep items")
    j.add_argument("--fit", type=int, choices=range(0, 6))
    j.add_argument("--status", choices=jobs.STATUSES, default="found")
    j = js.add_parser("set", help="update fields: lcb jobs set <id> status=applied next_action='follow up' next_date=2026-11-01")
    j.add_argument("id")
    j.add_argument("pairs", nargs="+")
    j = js.add_parser("note", help="append a dated note")
    j.add_argument("id")
    j.add_argument("text", nargs="+")
    j = js.add_parser("show", help="full record")
    j.add_argument("id")
    j = js.add_parser("rm", help="remove a record")
    j.add_argument("id")
    j = js.add_parser("profile", help="show / set the search profile (jobs/profile.json)")
    j.add_argument("--set", action="append")

    s = sub.add_parser("sd", help="system design: status / list / next / start / done / show")
    ss = s.add_subparsers(dest="sd_cmd")
    s.set_defaults(fn=cmd_sd)
    ss.add_parser("status")
    ss.add_parser("list")
    ss.add_parser("next")
    d = ss.add_parser("start", help="begin a session: creates design/notes/<slug>.md")
    d.add_argument("slug")
    d = ss.add_parser("done", help="record a session score 0-5 and schedule the re-visit")
    d.add_argument("slug")
    d.add_argument("--score", type=int, required=True, choices=range(0, 6))
    d.add_argument("--note")
    d = ss.add_parser("show", help="curriculum entry as JSON")
    d.add_argument("slug")

    s = sub.add_parser("open", help="open the problem in a browser")
    s.add_argument("slug", nargs="?")
    s.set_defaults(fn=cmd_open)
    return p


def cmd_jobs(a) -> int:
    sub = a.jobs_cmd
    try:
        if sub is None or sub == "board":
            print(jobs.board(show_all=getattr(a, "all", False)))
        elif sub == "add":
            j = jobs.add(a.company, a.title, url=a.url, location=a.location, remote=a.remote, salary=a.salary,
                         level=a.level, source=a.source, status=a.status, fit=a.fit, fit_notes=a.fit_notes,
                         interview_format=a.interview_format, prep=a.prep, next_action=a.next_action, next_date=a.next_date)
            if a.note:
                jobs.add_note(j["id"], a.note)
            print(f"added {j['id']}")
            readme.write()
        elif sub == "set":
            kv = {}
            for item in a.pairs:
                k, _, v = item.partition("=")
                kv[k] = v
            j = jobs.set_fields(a.id, **kv)
            print(jobs.show(j["id"]))
            readme.write()
        elif sub == "note":
            j = jobs.add_note(a.id, " ".join(a.text))
            print(f"noted on {j['id']}")
        elif sub == "show":
            print(jobs.show(a.id))
        elif sub == "rm":
            j = jobs.remove(a.id)
            print(f"removed {j['id']}")
            readme.write()
        elif sub == "profile":
            prof = jobs.load_profile()
            if a.set:
                for item in a.set:
                    k, _, v = item.partition("=")
                    try:
                        prof[k] = json.loads(v)
                    except json.JSONDecodeError:
                        prof[k] = v
                jobs.save_profile(prof)
            print(json.dumps(prof, indent=2, ensure_ascii=False))
    except KeyError as e:
        return _die(str(e))
    return 0


def cmd_sd(a) -> int:
    sub = a.sd_cmd
    try:
        if sub is None or sub == "status":
            print(design.status_text())
        elif sub == "list":
            print(design.list_text())
        elif sub == "next":
            nxt = design.next_items()
            for s in nxt["review"]:
                c = design.BY_SLUG[s]
                print(f"🔁 re-visit  {s}  {c['title']} ({c['zh']})")
            for s in nxt["in_progress"]:
                c = design.BY_SLUG[s]
                print(f"🔧 in progress  {s}  {c['title']} ({c['zh']})")
            if nxt["new"]:
                c = design.BY_SLUG[nxt["new"]]
                print(f"⬜ next  {c['slug']}  {c['title']} ({c['zh']}) [{c['kind']}]")
                for g in c.get("goals", c.get("focus", [])):
                    print(f"     - {g}")
                if c.get("refs"):
                    print("     refs: " + "; ".join(c["refs"]))
            if nxt.get("project"):
                c = design.BY_SLUG[nxt["project"]]
                print(f"🗣 resume deep dive (any time)  {c['slug']}  {c['title']}")
        elif sub == "start":
            r = design.start(a.slug)
            print(f"{r['slug']}: session {r['session']} started → {r['note'].relative_to(design.ROOT)}")
            readme.write()
        elif sub == "done":
            st = design.done(a.slug, a.score, a.note or "")
            print(f"{a.slug}: recorded {a.score}/5 (best {st['best']}); "
                  + (f"re-visit {st['next_review']}" if st["next_review"] else "no further re-visit scheduled"))
            readme.write()
        elif sub == "show":
            c = design.BY_SLUG.get(a.slug)
            if not c:
                return _die(f"unknown topic {a.slug!r}")
            print(json.dumps(c, indent=2, ensure_ascii=False))
    except KeyError as e:
        return _die(str(e))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.fn(args)
    except KeyError as e:
        return _die(str(e))
    except KeyboardInterrupt:
        return 130
