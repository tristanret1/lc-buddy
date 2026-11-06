"""Build problems/0x3f.json from the transcribed 灵茶山艾府 lists in problems/0x3f/*.txt.

Text format (one file per list):
    = <list name> | <key> | <source url>
    # chapter          (一、二、…)
    ## section         (§1.1 …)
    ### sub-label      (思维扩展 / 进阶 / §2.1.1 …)
    <id>. <title> [rating] [notes]        e.g.  1456. 定长子串中元音的最大数目 1263
IDs may be numeric, or cn-only forms like "LCP 68", "LCR 180", "面试题 16.06", "LCS 03", "九坤-04".

Slugs/difficulty/premium come from problems/catalog.json (leetcode.com catalogue, `lcb catalog`).
Run:  python3 -m lcb.import_0x3f
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "problems" / "0x3f"
CATALOG = ROOT / "problems" / "catalog.json"
OUT = ROOT / "problems" / "0x3f.json"

ID_RE = re.compile(r"^((?:LCP|LCR|LCS) \d+|面试题 [\d.]+|九坤-\d+|\d+)\.\s+(.*)$")
NOTE_STARTS = ("做到", "非暴力", "二分做法", "贪心做法", "快速沃尔什", "有 ", "有O", "有简单", "同 ", "推荐", "两种", "做法", "思考题", "见", "注", "需",
               "可以", "证明", "变形", "进阶", "结论", "类似", "联系", "本质", "暴搜", "解决", "包含", "附", "模板题",
               "经典题", "入门题", "例题", "转化", "优化", "字典序", "环形", "换根", "拓扑", "树上", "网格图", "扫描线",
               "状压", "浮点", "避免", "如何", "为下面", "为 ", "要求", "先做", "手写", "和下面", "想一想", "考虑",
               "倒序", "一对", "多对", "最小割", "二分图", "带权", "西北角", "凸优化", "调和", "巴什", "费马", "欧拉",
               "四平方", "类欧", "裴蜀", "倍数容斥", "莫比乌斯", "第一类", "第二类", "多重集", "试填", "构造", "组合公式",
               "扩展卢卡斯", "拓扑序", "旋转卡壳", "FFT", "根号分解", "回滚莫队", "线段树", "差分树状", "前 k 小", "静态二维",
               "CDQ", "康托", "曼哈顿", "二维树状", "时间戳", "离散化", "第 k 小", "pair", "bitset", "k 个指针", "子串的子串",
               "双向广搜", "三色标记", "刷表法", "记忆化", "单调性", "容斥", "字符串哈希", "闵可夫斯基", "Slope", "拉格朗日",
               "斜向", "商分", "HH", "矩形面积", "置换", "逻辑推理", "数学推导", "约瑟夫", "连分数", "解方程", "Gale", "Erdős",
               "三元环", "无平方因子", "LogTrick", "logTrick", "理解原理", "动态加边", "相邻相关", "式子变形", "状态设计",
               "分层图", "也可以", "也有", "不需要", "引入", "用栈", "用 DP", "用 LIS", "用 LCS", "基于", "相同元素",
               "k=", "k 从", "与 ", "实际", "难度", "O(", "IOI", "求个数", "求和", "混合背包", "多背包", "二维背包",
               "至少装满", "同 CF", "改成", "删除", "看我", "答疑", "原题", "只有", "从低", "最大改成", "是否", "结合",
               "结论好猜", "横看", "非暴力写法", "代码复用", "通用做法", "把 3", "绝对值的几何", "跳跃游戏")


def split_line(rest: str) -> tuple[str, int | None, bool, str, bool]:
    """-> (title, rating, approx_rating, note, premium)"""
    premium = "（会员题）" in rest or "(会员题)" in rest
    rest = rest.replace("（会员题）", " ").replace("(会员题)", " ").strip()
    toks = rest.split()
    rating, approx, split_at, extra_note = None, False, None, []
    for i, t in enumerate(toks):
        if i == 0 or not re.fullmatch(r"\d{4}", t):
            continue
        v = int(t)
        if not 1000 <= v <= 3600:
            continue
        prev = toks[i - 1]
        nxt = toks[i + 1] if i + 1 < len(toks) else ""
        if prev in ("同", "类似", "联系", "与", "和", "见", "第", "是", "题") or nxt.startswith("题"):
            continue
        rating, split_at = v, i
        if prev.endswith("约"):  # "约 1700" / "非暴力做法约 2300"
            approx, split_at = True, i - 1
            if prev[:-1]:
                extra_note.append(prev[:-1])
        break
    if split_at is not None:
        title_toks = toks[:split_at]
        rest_toks = toks[split_at + (2 if approx else 1):]
    else:
        title_toks, rest_toks = list(toks), []
    # peel a trailing note off the title heuristically ("移山所需的最少秒数 二分做法估计")
    note_toks = []
    for j in range(1, len(title_toks)):
        tail = " ".join(title_toks[j:])
        if len("".join(title_toks[:j])) < 2:
            continue  # "全 O(1) 的数据结构"
        if title_toks[j - 1] in ("-", "·") or title_toks[j] in ("I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX"):
            continue  # "合并两个二维数组 - 求和法", roman-numeral suffixes are part of the title
        if tail.startswith(NOTE_STARTS):
            title_toks, note_toks = title_toks[:j], title_toks[j:]
            break
    title = " ".join(title_toks)
    note = " ".join(note_toks + extra_note + rest_toks)
    return title, rating, approx, note, premium


def parse_file(path: Path) -> dict:
    lists = None
    chapter = section = sub = ""
    entries = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("= "):
            name, key, url = [x.strip() for x in line[2:].split("|")]
            lists = {"name": name, "key": key, "url": url, "file": path.name}
        elif line.startswith("### "):
            sub = line[4:].strip()
        elif line.startswith("## "):
            section, sub = line[3:].strip(), ""
        elif line.startswith("# "):
            chapter, section, sub = line[2:].strip(), "", ""
        else:
            m = ID_RE.match(line)
            if not m:
                print(f"  ?? unparsed line in {path.name}: {line}", file=sys.stderr)
                continue
            pid, rest = m.group(1), m.group(2)
            title, rating, approx, note, premium = split_line(rest)
            entries.append({"id": pid, "title": title, "rating": rating, "approx": approx, "note": note,
                            "premium_flag": premium, "path": " / ".join(x for x in (chapter, section, sub) if x)})
    assert lists, f"{path} lacks a '= name | key | url' header"
    lists["entries"] = entries
    return lists


def build() -> dict:
    catalog = json.loads(CATALOG.read_text()) if CATALOG.exists() else {}
    if not catalog:
        print("warning: problems/catalog.json missing — run `python3 -m lcb catalog` first; slugs will be empty", file=sys.stderr)
    files = sorted(SRC_DIR.glob("*.txt"))
    problems: dict[str, dict] = {}
    lists_out = []
    order = 0
    for f in files:
        L = parse_file(f)
        sections: dict[str, list] = {}
        for e in L["entries"]:
            pid = e["id"]
            cat = catalog.get(pid)
            cn_only = not pid.isdigit()
            key = pid  # unique key: the id itself (slug may be unknown for cn-only)
            if key not in problems:
                problems[key] = {
                    "id": pid,
                    "slug": cat["slug"] if cat else None,
                    "title": e["title"],
                    "title_en": cat["title"] if cat else None,
                    "difficulty": cat["difficulty"] if cat else None,
                    "rating": e["rating"],
                    "rating_approx": e["approx"],
                    "premium": bool(cat["premium"]) if cat else e["premium_flag"],
                    "cn_only": cn_only,
                    "topic": L["name"],
                    "list": L["key"],
                    "section": e["path"],
                    "note": e["note"],
                    "order": order,
                    "also_in": [],
                }
                order += 1
            else:
                p = problems[key]
                if p["rating"] is None and e["rating"]:
                    p["rating"] = e["rating"]
                tag = f"{L['key']} / {e['path']}"
                if L["key"] != p["list"] or e["path"] != p["section"]:
                    if tag not in p["also_in"]:
                        p["also_in"].append(tag)
            sections.setdefault(e["path"], []).append({"id": pid, "note": e["note"]})
        lists_out.append({"key": L["key"], "name": L["name"], "url": L["url"],
                          "count": len(L["entries"]),
                          "sections": [{"path": k, "ids": [x["id"] for x in v]} for k, v in sections.items()]})
        print(f"{L['name']:<14} {len(L['entries']):>4} entries, {len(sections)} sections")
    plist = list(problems.values())
    missing = [p["id"] for p in plist if not p["slug"] and not p["cn_only"]]
    if missing:
        print(f"warning: {len(missing)} numeric ids not in catalog: {missing[:20]}", file=sys.stderr)
    return {
        "name": "灵茶山艾府题单",
        "kind": "0x3f",
        "source": "https://leetcode.cn/discuss/post/9oZFK9/",
        "description": "灵茶山艾府（0x3f）的 12 个分类题单，按算法专题与难度分排序。",
        "lists": lists_out,
        "problems": plist,
    }


def main() -> int:
    data = build()
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=0) + "\n", encoding="utf-8")
    n = len(data["problems"])
    cn = sum(p["cn_only"] for p in data["problems"])
    prem = sum(p["premium"] for p in data["problems"])
    rated = sum(p["rating"] is not None for p in data["problems"])
    print(f"wrote {OUT.relative_to(ROOT)}: {n} unique problems ({cn} cn-only, {prem} premium, {rated} with rating)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
