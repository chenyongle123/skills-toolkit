#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scan_doc.py — delivery-audit M 层扫描器

用途：对任意 Markdown / 纯文本文档做机械检查，零语义判断。
      M1 引用可达  M2 计数自洽  M3 契约同构  M4 落盘对应  M5 枚举覆盖  M6 版本一致
      M7 回归标记（防假修复：用 JSON 钉死『错词必须消失 / 对词必须在某节出现』）

用法：
    python scan_doc.py 文档.md
    python scan_doc.py 文档.md --json 结果.json
    python scan_doc.py 文档.md --root E:/some/project   # 路径存在性检查根目录
    python scan_doc.py 文档.md --markers 回归清单.json   # 自定义 M7 标记；缺省自动加载同目录 regression_markers.json

设计原则：
    - 只报"确定的问题"与"待人工判断的候选"，不猜语义
    - 不硬编码任何项目结构，任何 md 文档通用
    - 退出码：0 无问题；1 有问题（便于 CI / 批处理）
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict

CN_NUM = {
    "零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
}


def cn2int(s):
    """中文/阿拉伯数字转 int，支持 十/十一/二十/二十三 之类。"""
    s = s.strip()
    if s.isdigit():
        return int(s)
    if not s:
        return None
    if "十" in s:
        left, _, right = s.partition("十")
        tens = CN_NUM.get(left, 1) if left else 1
        ones = CN_NUM.get(right, 0) if right else 0
        return tens * 10 + ones
    if len(s) == 1:
        return CN_NUM.get(s)
    return None


HEAD_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
NUM_HEAD_RE = re.compile(r"^(\d+(?:\.\d+)*)[.、\s]*")
REF_RE = re.compile(r"§\s*(\d+(?:\.\d+)*)")
# 数字+量词：同时接受阿拉伯与中文数字
QTY_RE = re.compile(
    r"([0-9]+|[零一二两三四五六七八九十]{1,3})\s*(条|项|类|处|件|个|人日|份|页|档|步|层|种|章|节|轮)"
)
DECL_PAREN_RE = re.compile(
    r"[（(]\s*([0-9]+|[一二两三四五六七八九十]{1,3})\s*(类|项|条|处|件|步|层|档)[)）]"
)
# 标题中不带括号的声明，如「能自动查的五件事」「三个人工关卡」
# 仅收中文数字：阿拉伯数字常出现在「残留 1 处」「拍板的 1 项」这类叙述里，误报率高
# 「处(?!理)」避免把「v0.4 处理」的「4 处」当量词
DECL_TITLE_RE = re.compile(
    r"([一二两三四五六七八九十]{1,3})\s*(类|项|条|处(?!理)|件|步|层|档)"
)


def load_lines(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read().splitlines()


def collect_headings(lines):
    """返回 [{line, level, number, title}]；number 为 None 表示无编号标题。"""
    out = []
    in_fence = False
    for i, ln in enumerate(lines, 1):
        if ln.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = HEAD_RE.match(ln)
        if not m:
            continue
        level = len(m.group(1))
        title = m.group(2)
        nm = NUM_HEAD_RE.match(title)
        number = nm.group(1) if nm else None
        out.append({"line": i, "level": level, "number": number, "title": title})
    return out


def check_refs(lines, heads):
    """M1：§X.Y 引用是否指向存在的节；同时给出目标标题供人工判语义。"""
    exist = {}
    for h in heads:
        if h["number"]:
            exist[h["number"]] = h
    problems, ok = [], []
    in_fence = False
    for i, ln in enumerate(lines, 1):
        if ln.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for m in REF_RE.finditer(ln):
            ref = m.group(1)
            ctx = ln[max(0, m.start() - 24): m.end() + 24].strip()
            if ref in exist:
                ok.append({
                    "ref": ref, "line": i, "context": ctx,
                    "target_title": exist[ref]["title"],
                    "target_line": exist[ref]["line"],
                })
            else:
                problems.append({"ref": ref, "line": i, "context": ctx})
    return problems, ok


def section_body(lines, heads, idx):
    """取第 idx 个标题到下一个同级或更高级标题之间的行。"""
    start = heads[idx]["line"]
    level = heads[idx]["level"]
    end = len(lines) + 1
    for h in heads[idx + 1:]:
        if h["level"] <= level:
            end = h["line"]
            break
    return lines[start:end - 1]


def child_headings(heads, idx):
    """本节直接下级标题的个数（"六条铁律"常以 6 个 ### 呈现，而非 6 个列表项）。"""
    level = heads[idx]["level"]
    count = 0
    for h in heads[idx + 1:]:
        if h["level"] <= level:
            break
        if h["level"] == level + 1:
            count += 1
    return count


def count_items(body):
    """数一节里的表格数据行与列表项。
    - 每个表格块的**第一行视为表头，不计**（一节里可能有多张表）
    - 首列为空的跨行续行不计
    - 只数顶层列表项，嵌套子项不计
    """
    table_rows = 0
    list_items = 0
    in_fence = False
    in_table = False
    for ln in body:
        s = ln.strip()
        if s.startswith("```"):
            in_fence = not in_fence
            in_table = False
            continue
        if in_fence:
            continue
        if s.startswith("|"):
            # 表头分隔行 |---|---|
            if re.match(r"^\|[\s:\-\|]+\|?$", s):
                continue
            cells = [c.strip() for c in s.strip("|").split("|")]
            if not in_table:
                in_table = True      # 本表第一行 = 表头
                continue
            if cells and cells[0] == "":
                continue             # 跨行续行
            table_rows += 1
        else:
            in_table = False
            if re.match(r"^[-*+]\s+", ln.rstrip()) or re.match(r"^\d+\.\s+", ln.rstrip()):
                list_items += 1
    return table_rows, list_items


def check_declared_counts(lines, heads):
    """M2(a)：标题里声称的 N 类/N 项 与本节点条目数是否吻合。"""
    problems, ok = [], []
    for idx, h in enumerate(heads):
        title = h["title"]
        m = DECL_PAREN_RE.search(title)
        if not m:
            # 无括号声明：仅当标题中恰好出现一处、且该短语处于标题收尾位置时才可判。
            # 「……的 1 项」「残留 1 处」这类是叙述而非声明，跳过以免误报。
            cands = [c for c in DECL_TITLE_RE.finditer(title)
                     if re.match(r"\s*([（(：:—\-]|$)", title[c.end():])]
            if len(cands) != 1:
                continue
            m = cands[0]
        declared = cn2int(m.group(1))
        if declared is None:
            continue
        body = section_body(lines, heads, idx)
        rows, items = count_items(body)
        subs = child_headings(heads, idx)
        # count_items 已排除每张表的表头，rows 即数据行数
        actual_table = rows
        rec = {"line": h["line"], "title": title, "declared": declared,
               "table": actual_table, "list": items, "subheadings": subs}
        if declared in (actual_table, items, subs):
            ok.append(rec)
        else:
            problems.append(rec)
    return problems, ok


def check_qty_census(lines):
    """M2(b)：全文 数字+量词 普查，按量词分组，供人工扫口径冲突。"""
    census = defaultdict(lambda: defaultdict(list))
    in_fence = False
    for i, ln in enumerate(lines, 1):
        if ln.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for m in QTY_RE.finditer(ln):
            v = cn2int(m.group(1))
            if v is None:
                continue
            unit = m.group(2)
            ctx = ln[max(0, m.start() - 14): m.end() + 10].strip()
            census[unit][v].append({"line": i, "context": ctx})
    return census


def check_json_blocks(lines):
    """M3：抽取所有 json 代码块，输出 key 集合；疑似同契约但字段不同则报警。"""
    blocks = []
    in_fence, buf, start, lang = False, [], 0, ""
    for i, ln in enumerate(lines, 1):
        s = ln.strip()
        if s.startswith("```"):
            if not in_fence:
                in_fence, buf, start, lang = True, [], i, s[3:].strip().lower()
            else:
                in_fence = False
                if lang in ("json", "jsonc"):
                    text = "\n".join(buf)
                    keys = re.findall(r'"([A-Za-z_][A-Za-z0-9_]*)"\s*:', text)
                    blocks.append({"start": start, "end": i,
                                   "keys": sorted(set(keys)), "text": text})
                buf = []
            continue
        if in_fence:
            buf.append(ln)

    suspects = []
    for a in range(len(blocks)):
        for b in range(a + 1, len(blocks)):
            ka, kb = set(blocks[a]["keys"]), set(blocks[b]["keys"])
            if not ka or not kb:
                continue
            inter = len(ka & kb)
            union = len(ka | kb)
            ratio = inter / union if union else 0
            # 部分重合：像同一契约但字段不全同
            if 0.25 <= ratio < 1.0:
                suspects.append({
                    "a": blocks[a]["start"], "b": blocks[b]["start"],
                    "only_a": sorted(ka - kb), "only_b": sorted(kb - ka),
                    "overlap": round(ratio, 2),
                })
    return blocks, suspects


PATH_RE = re.compile(r"`([^`\s]+\.(?:md|json|ya?ml|py|sh|txt|docx|xlsx|pptx|pdf))`")


def check_paths(lines, root):
    """M4：反引号内看起来像文件名的串，检查是否存在于 root。计划类文档产物名会大面积报缺，故仅提示。"""
    if not root:
        return None
    found, missing = [], []
    for i, ln in enumerate(lines, 1):
        for m in PATH_RE.finditer(ln):
            p = m.group(1)
            if "://" in p or p.startswith("~"):
                continue
            full = os.path.join(root, p)
            (found if os.path.exists(full) else missing).append({"line": i, "path": p})
    return {"found": found, "missing": missing}


def check_terminology(lines):
    """M5(b)：列出所有 snake_case 字段名并按前缀分组，供人工判断是否同一概念多写法。
    只做清单，不自动判冲突（避免误报降低可信度）。"""
    groups = defaultdict(set)
    where = defaultdict(list)
    for i, ln in enumerate(lines, 1):
        for m in re.finditer(r"\b([a-z][a-z0-9]*)_([a-z][a-z0-9_]*)\b", ln):
            groups[m.group(1)].add(m.group(0))
            where[m.group(0)].append(i)
    multi = {k: sorted(v) for k, v in groups.items() if len(v) > 1}
    return multi, where


DOCVER_RE = re.compile(r"v(\d+\.\d+(?:\.\d+)?)")


def check_version_consistency(lines):
    """M6：表头里出现的版本号若与文档自身版本不一致，提示人工确认为历史陈述。

    典型漏检：章节重排后表头仍写旧版本（如文档已到 v0.9，表头写「v0.4 处理」）。
    只查表格表头行——正文里的历史版本号（变更记录、比对表）属正常，不报。
    """
    doc_ver = None
    # 优先认显式的"版本：vX"声明（可带 技能/文档 前缀、可带 ** 强调）；
    # "对照版本""被审版本"这类是别人的版本，不认。
    own_ver_re = re.compile(
        r"(?:^|>)\s*\*{0,2}(?:技能|文档)?版本\*{0,2}：\s*\*{0,2}v(\d+\.\d+(?:\.\d+)?)")
    for ln in lines:
        m = own_ver_re.search(ln)
        if m:
            doc_ver = m.group(1)
            break
    if doc_ver is None:
        for ln in lines:
            if not ln.lstrip().startswith("#"):
                continue
            # 标题里的版本号若出现在"意见/审核/审查/判断/对照/说明"类文档里，
            # 指的是被审对象，不是本文档自身版本——认错会误报，故跳过。
            if re.search(r"意见|审核|审查|判断|对照|说明", ln):
                return None, []
            m = DOCVER_RE.search(ln)
            if m:
                doc_ver = m.group(1)
            break
    if doc_ver is None:
        return None, []

    hits = []
    in_fence = False
    for i in range(len(lines) - 1):
        s = lines[i].strip()
        if s.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        nxt = lines[i + 1].strip()
        # 表头行 = 下一行是 |---|---| 分隔行
        if s.startswith("|") and re.match(r"^\|[\s:\-\|]+\|?$", nxt):
            found = [m.group(1) for m in DOCVER_RE.finditer(s)]
            # 一行里并列多个版本 = 版本对照表，属正常；只报"单一旧版本"的残留
            if len(set(found)) >= 2:
                continue
            for v in found:
                if v != doc_ver:
                    hits.append({"line": i + 1, "version": v, "text": s})
    return doc_ver, hits


def section_for_scope(heads, scope):
    """返回匹配 scope 的标题索引列表。
    scope 可为数字编号（如 '3.6'）或标题包含的片段（如 'B.1'）。"""
    idxs = []
    for i, h in enumerate(heads):
        if h["number"] == scope:
            idxs.append(i)
        elif scope in h["title"]:
            idxs.append(i)
    return idxs


def check_regression_markers(lines, heads, markers):
    """M7：对照 JSON 标记，验证『声称已修』的缺陷正文落点真被修掉（防假修复）。
    - checks[]：对每个 scope 节，must_contain 必须全在、must_not_contain 必须全不在。
    - global_absent_except_changelog：错词全文不得出现，但允许在 §0 变更记录里作『改自何处』描述。
    """
    problems, ok = [], []
    for c in markers.get("checks", []):
        scope = c.get("scope")
        idxs = section_for_scope(heads, scope) if scope else []
        if not idxs:
            problems.append({"id": c.get("id"), "scope": scope,
                             "error": "未找到目标节，跳过该检查"})
            continue
        body = []
        for idx in idxs:
            body.extend(section_body(lines, heads, idx))
        text = "\n".join(body)
        miss = [n for n in c.get("must_contain", []) if n not in text]
        bad = [n for n in c.get("must_not_contain", []) if n in text]
        rec = {"id": c.get("id"), "scope": scope, "missing": miss, "forbidden_found": bad}
        (problems if (miss or bad) else ok).append(rec)

    ga = markers.get("global_absent_except_changelog")
    if ga:
        phrases = ga.get("phrases", [])
        changelog_idxs = [i for i, h in enumerate(heads)
                          if (h["number"] and h["number"].startswith("0"))
                          or "版本变更记录" in h["title"]]
        excluded = set()
        for idx in changelog_idxs:
            start = heads[idx]["line"]
            level = heads[idx]["level"]
            end = len(lines) + 1
            for h in heads[idx + 1:]:
                if h["level"] <= level:
                    end = h["line"]
                    break
            excluded.update(range(start, end))
        for ph in phrases:
            found = [i for i, ln in enumerate(lines, 1)
                     if i not in excluded and ph in ln]
            if found:
                problems.append({"id": "global_absent:" + ph, "phrase": ph,
                                 "found_lines": found[:10]})
            else:
                ok.append({"id": "global_absent:" + ph, "scope": "全文(除§0)"})
    return problems, ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--json", dest="json_out")
    ap.add_argument("--root", default=None)
    ap.add_argument("--markers", default=None,
                    help="M7 回归标记 JSON；缺省自动加载同目录 regression_markers.json")
    ap.add_argument("--ref-target", default=None,
                    help="用另一份文档的标题表校验 § 引用（审阅意见/施工清单类文档用）")
    args = ap.parse_args()

    if not os.path.exists(args.path):
        print("文件不存在：%s" % args.path)
        return 2

    lines = load_lines(args.path)
    heads = collect_headings(lines)

    # 审阅意见类文档引用的是"被审对象"的章节，需用对方的标题表来校验
    ref_heads = heads
    ref_src = "本文档"
    if args.ref_target and os.path.exists(args.ref_target):
        ref_heads = collect_headings(load_lines(args.ref_target))
        ref_src = os.path.basename(args.ref_target)

    ref_bad, ref_ok = check_refs(lines, ref_heads)
    decl_bad, decl_ok = check_declared_counts(lines, heads)
    census = check_qty_census(lines)
    blocks, suspects = check_json_blocks(lines)
    paths = check_paths(lines, args.root)

    # ---- M7 回归标记（防假修复）----
    markers = None
    markers_path = args.markers
    if not markers_path:
        sib = os.path.join(os.path.dirname(os.path.abspath(args.path)),
                           "regression_markers.json")
        if os.path.exists(sib):
            markers_path = sib
    if markers_path and os.path.exists(markers_path):
        try:
            markers = json.load(open(markers_path, encoding="utf-8"))
        except Exception as e:
            print("⚠️ 读取 markers 失败：%s" % e)
    m7_bad, m7_ok = check_regression_markers(lines, heads, markers) if markers else ([], [])

    print("=" * 68)
    print("scan_doc M 层扫描：%s" % os.path.basename(args.path))
    print("行数 %d ／ 标题 %d ／ §引用 %d" % (len(lines), len(heads), len(ref_bad) + len(ref_ok)))
    print("=" * 68)

    # ---- M1 ----
    print("\n【M1 引用可达】  引用目标：%s" % ref_src)
    if ref_bad:
        print("  ❌ 指向不存在的节：%d 处" % len(ref_bad))
        for p in ref_bad:
            print("     L%-5d %-6s  …%s…" % (p["line"], "§" + p["ref"], p["context"]))
    else:
        print("  ✅ 所有 § 引用均指向存在的节")
    if ref_ok:
        print("  ⚠️ 存在但需人工判语义（%d 处，看引用语境与目标标题是否对得上）：" % len(ref_ok))
        seen = set()
        for o in ref_ok:
            key = (o["ref"], o["line"])
            if key in seen:
                continue
            seen.add(key)
            print("     L%-5d §%-6s 目标=「%s」 引用语境：…%s…"
                  % (o["line"], o["ref"], o["target_title"][:28], o["context"]))

    # ---- M2 ----
    print("\n【M2 计数自洽】")
    if decl_bad:
        print("  ❌ 标题声明数与本节条目数不符：%d 处" % len(decl_bad))
        for p in decl_bad:
            print("     L%-5d 声明 %d ／ 表格 %d 行 ／ 列表 %d 项 ／ 子标题 %d 个 —— %s"
                  % (p["line"], p["declared"], p["table"], p["list"], p["subheadings"], p["title"][:40]))
    else:
        print("  ✅ 标题声明数与条目数一致")
    print("  ⚠️ 量词普查（同一量词出现多个数值＝可能口径冲突）：")
    for unit, vals in sorted(census.items(), key=lambda x: -sum(len(v) for v in x[1].values())):
        nums = sorted(vals.keys())
        if len(nums) <= 1:
            continue
        flag = "  ← 需核" if len(nums) > 2 else ""
        shown = ", ".join("%s×%d" % (n, len(vals[n])) for n in nums)
        print("     「%s」%s%s" % (unit, shown, flag))
        for n in nums:
            ev = vals[n][0]
            print("         %s → L%d  %s" % (n, ev["line"], ev["context"][:56]))

    # ---- M3 ----
    print("\n【M3 契约同构】")
    if suspects:
        print("  ⚠️ 疑似同一契约但字段集合不同：%d 对" % len(suspects))
        for s in suspects:
            print("     块 L%d ↔ L%d  重合度 %.2f" % (s["a"], s["b"], s["overlap"]))
            if s["only_a"]:
                print("        仅前者有：%s" % ", ".join(s["only_a"]))
            if s["only_b"]:
                print("        仅后者有：%s" % ", ".join(s["only_b"]))
    else:
        print("  ✅ 未发现字段集合明显冲突的 json 块")
    print("  （边界：本项只比对 ```json 代码块；若同一契约在别处以表格/散文形式出现，"
        "脚本抓不到，须人工比对）")

    # ---- M4 ----
    print("\n【M4 落盘对应】")
    if paths is None:
        print("  ⚠️ 未启用（加 --root <目录> 可检查反引号文件名是否存在）")
    elif paths["missing"]:
        print("  ⚠️ 提示：%d 个反引号文件名未在 root 下找到（计划类文档中产物名属正常）"
              % len(paths["missing"]))
        for p in paths["missing"][:12]:
            print("     L%-5d %s" % (p["line"], p["path"]))
        if len(paths["missing"]) > 12:
            print("     … 其余 %d 条省略" % (len(paths["missing"]) - 12))
    else:
        print("  ✅ 反引号文件名均可在 root 下找到")

    # ---- M5 ----
    print("\n【M5 枚举覆盖】")
    term, where = check_terminology(lines)
    if term:
        print("  ⚠️ 同一前缀下出现多个字段名（请人工确认是否为同一概念的不同写法）：")
        for k, v in list(term.items())[:10]:
            print("     %s_* : %s" % (k, " / ".join(v)))
    else:
        print("  ✅ 未发现同前缀字段名多写法")
    print("  （「声称 N 档/类」是否真有 N 个枚举值，需人工核对；标题声明数异常见上方 M2）")

    # ---- M6 ----
    print("\n【M6 版本一致】")
    doc_ver, ver_hits = check_version_consistency(lines)
    if doc_ver is None:
        print("  ⚠️ 未在标题中识别到文档版本（形如 v1.2），跳过")
    elif ver_hits:
        print("  ⚠️ 表头出现与本文档（v%s）不一致的版本号，逐条确认是否为历史陈述：" % doc_ver)
        for h in ver_hits:
            print("     L%-5d v%s  —— %s" % (h["line"], h["version"], h["text"][:56]))
    else:
        print("  ✅ 表头版本号与文档版本一致（v%s）" % doc_ver)

    # ---- M7 ----
    print("\n【M7 回归标记（防假修复）】")
    if markers is None:
        print("  ⚠️ 未加载 markers（同目录无 regression_markers.json 且未传 --markers），跳过")
    elif m7_bad:
        print("  ❌ 标记未通过：%d 项" % len(m7_bad))
        for p in m7_bad:
            if "error" in p:
                print("     [%s] 节 %s：%s" % (p.get("id"), p.get("scope"), p["error"]))
            elif "phrase" in p:
                print("     [全局禁止] 「%s」仍在正文出现：%s"
                      % (p["phrase"], ", ".join("L%d" % x for x in p["found_lines"])))
            else:
                print("     [%s] 节 %s：缺 %s ／ 残留 %s"
                      % (p.get("id"), p.get("scope"), p.get("missing"), p.get("forbidden_found")))
    else:
        print("  ✅ 全部 %d 项标记通过（错词已消失、对词已落正文）" % len(m7_ok))
        for o in m7_ok:
            print("     · %s（%s）" % (o.get("id"), o.get("scope")))

    # ---- 汇总 ----
    total = len(ref_bad) + len(decl_bad) + len(suspects) + len(m7_bad)
    print("\n" + "=" * 68)
    print("硬问题合计：%d 处（引用失效 %d ／ 计数不符 %d ／ 契约冲突 %d ／ 回归标记 %d）"
          % (total, len(ref_bad), len(decl_bad), len(suspects), len(m7_bad)))
    print("提示项：待人工判语义的引用 %d 处、量词冲突 %d 组"
          % (len(ref_ok), sum(1 for v in census.values() if len(v) > 1)))
    print("=" * 68)

    if args.json_out:
        payload = {
            "file": args.path,
            "lines": len(lines),
            "m1_missing": ref_bad,
            "m1_semantic_check": ref_ok,
            "m2_declared_mismatch": decl_bad,
            "m2_qty_census": {u: {str(n): v for n, v in d.items()} for u, d in census.items()},
            "m3_blocks": [{"start": b["start"], "end": b["end"], "keys": b["keys"]} for b in blocks],
            "m3_suspects": suspects,
            "m4_paths": paths,
            "m5_terminology": term,
            "m6_version": {"doc": doc_ver, "header_mismatch": ver_hits},
        }
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print("JSON 已写入：%s" % args.json_out)

    return 0 if total == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
