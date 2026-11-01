# -*- coding: utf-8 -*-
"""
check_commit_lock.py —— ② bid-compliance-check 承诺锁校验（②-B · 新增检项）
对标本报告 P0-1：文章模块 2「全局事实锁 Global Truth Bus」。

与 `check_consistency.py`（**稿↔稿**互比）方向不同：本脚本是**锁→稿**——
以 ①/② 阶段人工确认的 `03d_commit-lock.json` 为基准，查成稿正文是否**照抄了锁定的承诺**。
价值：把「写完再检出矛盾、回退 ③ 改正文」前移为「写前锁死、写完校验」，
直接减少 ②-B 回退二（retry_count ≤2，耗尽转 exhausted）的消耗。

🔴 唯一实现原则：承诺锁校验只在本文件一处实现。

口径：只报「正文出现与锁定值不同的承诺」，**不替投标人决定哪个值是对的**——
若招标文件实际要求与锁不一致，应回 ① 改锁（G2 重确认），不是改正文。

输入：--bid <项目/bid>（读 03d_commit-lock.json + 01c_format-outline.json + 05_chapters/*.md）
输出：06_compliance/commit-lock-check.md
rc：0=一致（或未启用锁，已明确提示）；1=存在 ⚠️ 项（G5 须闭环）；2=输入缺失
"""
import argparse
import datetime as _dt
import json
import os
import re
import sys
from collections import defaultdict

LOCK_FILE = "03d_commit-lock.json"


def parse_chapter(path: str) -> dict:
    text = open(path, encoding="utf-8").read()
    fm, body = {}, text
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.S)
    if m:
        body = m.group(2)
        for ln in m.group(1).splitlines():
            mm = re.match(r"^(\s*)([\w]+):\s*(.*)$", ln)
            if mm and not mm.group(1):
                fm[mm.group(2)] = mm.group(3).strip().strip("'\"")
    return {"frontmatter": fm,
            "paragraphs": [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]}


def norm_num(s: str) -> str:
    """数值归一：去空格、统一小数形态（用于「180」vs「180.0」不误报）。"""
    s = s.strip().replace(" ", "")
    try:
        f = float(s)
        return str(int(f)) if f.is_integer() else str(f)
    except ValueError:
        return s


def load_chapters(bid: str, outline: dict) -> list:
    ch_dir = os.path.join(bid, "05_chapters")
    by_id = {}
    for fn in sorted(os.listdir(ch_dir)):
        if fn.endswith(".md"):
            ch = parse_chapter(os.path.join(ch_dir, fn))
            by_id[ch["frontmatter"].get("chapter_id") or fn[:-3]] = ch
    out = []
    for node in outline.get("chapters", []):
        cid = str(node.get("id", ""))
        if cid in by_id:
            out.append({"id": cid, "number": str(node.get("number", "")),
                        "title": str(node.get("title", "")),
                        "paragraphs": by_id[cid]["paragraphs"]})
    return out


def check_numbers(chapters: list, locks: list) -> tuple:
    """核心数字锁：正文中同义表述旁的数值 ≠ 锁定值 → ⚠️（给位置）。"""
    warns, ok = [], []
    for item in locks or []:
        key = str(item.get("key", "")).strip()
        unit = str(item.get("unit", "")).strip()
        lock_v = norm_num(str(item.get("value", "")).strip())
        syns = [s for s in (item.get("synonyms") or []) if str(s).strip()] or [key]
        if not key or not lock_v:
            continue
        pat = re.compile(r"(?:%s)[^。；;\n]{0,25}?(\d+(?:\.\d+)?)\s*%s" % (
            "|".join(re.escape(s) for s in syns), re.escape(unit)))
        found = defaultdict(list)
        for ch in chapters:
            for pi, p in enumerate(ch["paragraphs"]):
                for m in pat.finditer(p):
                    v = norm_num(m.group(1))
                    if v and v != lock_v:
                        found[v].append(f"{ch['number']}{ch['title']}（`{ch['id']}`）· 第 {pi + 1} 段："
                                        f"…{m.group(0)[:40]}…")
        if found:
            for v, locs in sorted(found.items()):
                warns.append(f"承诺数字偏离：{key} 锁定 {lock_v}{unit}，正文出现 {v}{unit}"
                             f"（{len(locs)} 处）——{'；'.join(locs[:3])}"
                             f"{'…' if len(locs) > 3 else ''}")
        else:
            ok.append(f"{key}＝{lock_v}{unit}")
    return warns, ok


def check_terms(chapters: list, words: list, label: str) -> list:
    """禁词扫描（技术路线禁词 / 禁用自称）。给位置，只报信号。"""
    warns = []
    for w in [x for x in (words or []) if str(x).strip()]:
        hits = []
        for ch in chapters:
            for pi, p in enumerate(ch["paragraphs"]):
                if w in p:
                    hits.append(f"{ch['number']}{ch['title']}（`{ch['id']}`）· 第 {pi + 1} 段")
        if hits:
            warns.append(f"{label}命中「{w}」（{len(hits)} 处）——{'；'.join(hits[:3])}"
                         f"{'…' if len(hits) > 3 else ''}")
    return warns


def render(res: dict, bid: str) -> str:
    md = ["# 承诺锁校验（②-B · 锁→稿）", "",
          f"> 生成：bid-compliance-check check_commit_lock；bid：`{bid}`；"
          f"时间：{_dt.datetime.now().astimezone().replace(microsecond=0).isoformat()}",
          "> 基准：`03d_commit-lock.json`（G2 人工确认后只读）。只报「正文与锁定值不一致」，"
          "**不替投标人决定取哪个值**——若招标文件实际要求与锁冲突，应回 ① 改锁并重确认。", ""]
    md += ["## 一、核心数字锁", ""]
    if res["num_ok"]:
        for s in res["num_ok"]:
            md.append(f"- ✅ {s}（正文未见偏离值）")
    if not res["num_ok"] and not res["num_warns"]:
        md.append("- 未配置数字锁或正文未出现可匹配表述")
    md += ["", "## 二、技术路线锁", ""]
    md.append("- " + ("无禁用技术词配置" if not res.get("tech_forbidden")
                      else f"禁用词：{'、'.join(res['tech_forbidden'])}"))
    md += ["", "## 三、命名实体锁", ""]
    md.append("- 我方自称锁定：" + (res.get("self_ref") or "（未配置）"))
    md.append("- " + ("无禁用自称配置" if not res.get("name_forbidden")
                      else f"禁用自称：{'、'.join(res['name_forbidden'])}"))
    if res["warns"]:
        md += ["", "## 四、⚠️ 需人工处置项", ""]
        for w in res["warns"]:
            md.append(f"- {w}")
        md += ["", "> 处置：确认是**正文写错**（回 ③ 改正文）还是**锁错了**（回 ① 改锁并 G2 重确认）；"
                    "G5 逐条闭环后方可写 `recheck_confirmed`。"]
    else:
        md += ["", "## 四、结论", "", "- ✅ 未发现与承诺锁偏离的项"]
    return "\n".join(md) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bid", required=True, help="项目 bid 目录")
    args = ap.parse_args()
    bid = args.bid
    if not os.path.isdir(bid):
        print(f"【执行阻断】bid 目录不存在：{bid}")
        return 2
    lock_p = os.path.join(bid, LOCK_FILE)
    if not os.path.exists(lock_p):
        print(f"ℹ️ 未启用承诺锁（{LOCK_FILE} 不存在）：本项**未检**，不得视为已查。"
              f"跨章一致性仍由 check_consistency.py 兜底。")
        return 0
    o1c_p = os.path.join(bid, "01c_format-outline.json")
    if not os.path.exists(o1c_p):
        print("【执行阻断】01c_format-outline.json 缺失")
        return 2
    if not os.path.isdir(os.path.join(bid, "05_chapters")):
        print("【执行阻断】05_chapters/ 缺失（先完成 ③ 正文）")
        return 2
    lock = json.load(open(lock_p, encoding="utf-8"))
    outline = json.load(open(o1c_p, encoding="utf-8"))
    chapters = load_chapters(bid, outline)
    if not chapters:
        print("【执行阻断】05_chapters 按 01c 章序装载为空")
        return 2

    locks = (lock.get("locks") or {})
    num_warns, num_ok = check_numbers(chapters, locks.get("numbers"))
    tech = locks.get("tech_route") or {}
    naming = locks.get("naming") or {}
    warns = list(num_warns)
    warns += check_terms(chapters, tech.get("forbidden"), "技术路线禁词")
    warns += check_terms(chapters, naming.get("forbidden"), "禁用自称/称谓")
    res = {"num_warns": num_warns, "num_ok": num_ok, "warns": warns,
           "tech_forbidden": tech.get("forbidden"), "name_forbidden": naming.get("forbidden"),
           "self_ref": naming.get("self_ref")}
    out_dir = os.path.join(bid, "06_compliance")
    os.makedirs(out_dir, exist_ok=True)
    out_p = os.path.join(out_dir, "commit-lock-check.md")
    with open(out_p, "w", encoding="utf-8") as f:
        f.write(render(res, bid))
    print(f"承诺锁校验：章节 {len(chapters)} 个；数字锁 {len(num_ok)} 项一致；"
          f"⚠️ {len(warns)} 项（报告：{out_p}）")
    for w in warns:
        print("  ⚠️", w)
    return 1 if warns else 0


if __name__ == "__main__":
    sys.exit(main())
