#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
④ bid-docx-export — 脚本间共享模块（内部，下划线开头不对外）
=============================================================
供 assemble_pdf / export_docx / scrub_metadata / verify_docx 复用：
入口闸门（G5 / expired 联动 / style_source 一致）、样式档读取、
章节 frontmatter 解析、[[F:]]/[[S:]] 标注剔除。
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

STAGES_OK_EXPORT = ("recheck_confirmed",)

# 章节文件名：n-xxxx（可带 _标题 后缀，与 ③ word_count.py 同口径）
CHAPTER_FILE_RE = re.compile(r"^(n-[0-9a-f]{4})(?:_.*)?\.md$")


def _read_json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def read_skill_version() -> str:
    """读本技能 SKILL.md frontmatter version（scripts/ 上一级）。"""
    skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        with open(os.path.join(skill_dir, "SKILL.md"), encoding="utf-8") as f:
            m = re.search(r"^version:\s*(\d+\.\d+\.\d+)\s*$", f.read(), re.M)
            return m.group(1) if m else "?"
    except OSError:
        return "?"


def check_skill_lock() -> list:
    """运行时 skills-lock 版本自检（SKILL §六三级降级之一）。

    仓库内运行（技能根向上 ≤3 级有 skills-lock.json）→ 比对 lock 登记版本，
    不一致返回警告列表；独立分发（无 lock 文件）→ 信息态提示跳过。
    只报告，不猜、不改 lock。
    """
    skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    lock_p = None
    d = skill_dir
    for _ in range(3):
        d = os.path.dirname(d)
        cand = os.path.join(d, "skills-lock.json")
        if os.path.exists(cand):
            lock_p = cand
            break
    if not lock_p:
        return ["运行目录无 skills-lock.json（独立分发形态）：版本对齐自检跳过"]
    try:
        with open(lock_p, encoding="utf-8") as f:
            lk = json.load(f)
        reg = str(lk.get("skills", {}).get("bid-docx-export", {}).get("version", ""))
    except (OSError, json.JSONDecodeError, AttributeError) as e:
        return [f"skills-lock.json 不可解析（{e}）：版本对齐自检跳过"]
    v = read_skill_version()
    if reg and v != "?" and reg != v:
        return [f"版本不对齐：SKILL.md={v} vs skills-lock 登记={reg}"
                "（技能包与 lock 漂移；开发库内须 python tests/validate_contract.py 核对）"]
    return []


def replace_ev(text: str, ev_map: dict) -> str:
    """[[EV:ev-xxx]] → 见附件A-xx（第N–M页）（页码来自 pagination.json，先跑 assemble_pdf）。

    与 export_docx 同一实现（本模块为共享单一定义）；未映射的引用保留原样待查。
    """
    def _r(m):
        info = ev_map.get(m.group(1))
        if not info:
            return m.group(0)
        a, b = info[0], info[1]
        rng = f"第{a}页" if a == b else f"第{a}\u2013{b}页"
        return f"见附件{info[2]}（{rng}）"
    return re.sub(r"\[\[EV:(ev-\d+)\]\]", _r, text)


def pdf_identity_hits(pdf_path: str, identities: list) -> list:
    """暗标标识 PDF 文本层粗提扫描（verify/scrub 共用；外部扫描件常带公司名）。

    三种载体并扫：未压缩流的 UTF-8/UTF-16 原文；FlateDecode 流 zlib 解压后同前；
    本工具 BodyWriter 的 UCS2-BE hex 文本（<XXXX…> Tj）。仅报事实态命中供人工
    核对（位图型扫描件无文本层，机检天然覆盖不到，人工抽检兜底）。
    """
    import zlib
    with open(pdf_path, "rb") as f:
        data = f.read()
    hay = bytearray(data)
    for m in re.finditer(rb"stream\r?\n(.*?)endstream", data, re.S):
        seg = m.group(1)
        try:
            hay += zlib.decompress(seg)
        except Exception:
            hay += seg
    hits = []
    for ident in identities:
        if not ident:
            continue
        b16 = ident.encode("utf-16-be")
        needles = (ident.encode("utf-8"), b16, ident.encode("utf-16-le"),
                   b16.hex().upper().encode(), b16.hex().lower().encode())
        if any(n and n in hay for n in needles):
            hits.append(ident)
    return hits


def gate(bid: str) -> tuple[int, list[str], dict]:
    """导出链入口闸门。返回 (rc, 消息列表(fail+warn), metadata)。

    rc=0 放行；rc=2 阻断。warns 以 ⚠️ 前缀混入消息列表。
    检查项（SKILL §二）：00_metadata 存在、stage=recheck_confirmed、
    05_chapters 存在、06_compliance/form-check.md 存在且无空项、
    ②-A expired 未解决（联动阻断）、01c 在、style_source 一致。
    consistency-issues.md 缺失 → 信息态警告（②-B/check_consistency 产物，
    未经其跑过的旧管线放行但提示）。
    """
    fails = []
    warns = []
    meta_p = os.path.join(bid, "00_metadata.json")
    if not os.path.exists(meta_p):
        return 2, ["00_metadata.json 不存在（流水线未初始化）"], {}
    meta = _read_json(meta_p)
    stage = meta.get("stage", "")
    if stage not in STAGES_OK_EXPORT:
        fails.append(f"stage={stage or '(空)'}（导出要求 recheck_confirmed；未过成稿终检 G5 拒绝导出）")
    # 01c（章序基准，后续缺章/style_source 检查共用）
    o1c_p = os.path.join(bid, "01c_format-outline.json")
    outline = _read_json(o1c_p) if os.path.exists(o1c_p) else None
    if outline is None:
        fails.append("01c_format-outline.json 缺失")
    # 05_chapters：存在性 + 缺章 + 草稿态
    ch_dir = os.path.join(bid, "05_chapters")
    mds = [fn for fn in sorted(os.listdir(ch_dir))
           if os.path.isdir(ch_dir) and fn.endswith(".md")] if os.path.isdir(ch_dir) else []
    if not mds:
        fails.append("05_chapters/ 无章节文件（先完成 ③ 正文）")
    have_ids = set()
    not_final = []
    for fn in mds:
        m = CHAPTER_FILE_RE.match(fn)
        if m:
            have_ids.add(m.group(1))
        ch = parse_chapter(os.path.join(ch_dir, fn))
        if str(ch.get("frontmatter", {}).get("status", "")) != "final":
            not_final.append(ch["id"])
    if outline:
        want = {str(n.get("id", "")) for n in outline.get("chapters", []) if n.get("id")}
        miss = sorted(want - have_ids)
        if miss:
            fails.append(f"05_chapters 缺章 {len(miss)}/{len(want)}（01c 有节点而无章节文件）："
                         f"{'、'.join(miss[:6])}{'…' if len(miss) > 6 else ''}——回 ③ 补写")
    if mds and not_final:
        fails.append(f"存在 status≠final 章节 {len(not_final)}/{len(mds)}（未过 ③ 步 5 背对背复核；"
                     f"导出只接受 final）：{'、'.join(not_final[:6])}{'…' if len(not_final) > 6 else ''}")
    cdir = os.path.join(bid, "06_compliance")
    fc_p = os.path.join(cdir, "form-check.md")
    if not os.path.exists(fc_p):
        fails.append("06_compliance/form-check.md 缺失（先完成成稿终检 G5）")
    else:
        blanks = []
        for ln in open(fc_p, encoding="utf-8").read().splitlines():
            m = re.match(r"^-\s*.+?[：:]\s*(?:✅|⚠️|❌)?\s*(.*)$", ln)
            if m and (not m.group(1).strip() or m.group(1).strip() in ("—", "-", "无")):
                blanks.append(ln[:40])
        if blanks:
            fails.append(f"form-check.md 存在空项/未决项（{len(blanks)} 处）：{'；'.join(blanks[:3])}")
    if not os.path.exists(os.path.join(bid, "01c_format-outline.json")):
        fails.append("01c_format-outline.json 缺失")
    if not os.path.exists(os.path.join(cdir, "consistency-issues.md")):
        warns.append("06_compliance/consistency-issues.md 缺失（check_consistency 未跑或旧管线；建议先跑再导出）")
    # expired 联动（②-A 结论，不重判；契约：f_qual_timing.status=整体最坏态，items=条目明细）
    cr_p = os.path.join(cdir, "compliance-report.json")
    if os.path.exists(cr_p):
        try:
            fqt = _read_json(cr_p).get("f_qual_timing", [])
            expired = []
            if isinstance(fqt, dict):
                if str(fqt.get("status", "")) == "expired":
                    expired = list(fqt.get("items") or []) or [fqt]
                else:  # 条目级双保险（顶层缺 status 时逐条扫 state）
                    expired = [x for x in (fqt.get("items") or [])
                               if isinstance(x, dict) and str(x.get("state", "")) == "expired"]
            elif isinstance(fqt, list):
                expired = [x for x in fqt
                           if isinstance(x, dict) and str(x.get("state", x.get("status", ""))) == "expired"]
            if expired:
                fails.append(f"②-A 结论存在未解决 expired 项（{len(expired)} 条），阻断导出（④ 不重判时效，仅联动）")
        except (json.JSONDecodeError, OSError, AttributeError, TypeError):
            fails.append("compliance-report.json 的 f_qual_timing 无法解析（契约破坏；重跑 ② check_compliance 后再导出）")
    # style_source 一致性（build_style_profile 写回 00_metadata.style_source；01c 为基准）
    if outline is not None:
        typo_src = str((outline.get("typography") or {}).get("source", ""))
        ms = str(meta.get("style_source", ""))
        if typo_src and not ms:
            warns.append(f"00_metadata.style_source 缺失（build_style_profile 未跑或旧管线产物）："
                         f"当前 01c.typography.source={typo_src}")
        elif typo_src and ms and typo_src != ms:
            fails.append(f"style_source 不一致：metadata={ms} vs 01c.typography.source={typo_src}（记入 failed_nodes 阻断）")
            meta.setdefault("failed_nodes", []).append("style_source_mismatch")
    # skills-lock 运行时自检（SKILL §六：lock 缺失/不对齐 → 信息态警告不阻断）
    for w in check_skill_lock():
        warns.append(w)
    msgs = fails + [f"⚠️ {w}" for w in warns]
    return (2 if fails else 0), msgs, meta


def read_style_profile(bid: str) -> dict:
    """读 07_out/style-profile.yaml（简单解析：仅本技能生成的扁平/二层结构）。"""
    p = os.path.join(bid, "07_out", "style-profile.yaml")
    if not os.path.exists(p):
        return {}
    return parse_style_yaml(open(p, encoding="utf-8").read())


def parse_style_yaml(text: str) -> dict:
    """style-profile 系 yaml 子集解析（缩进二层 + 标量类型推断）。

    供 read_style_profile（运行期产物）与 build_style_profile（内置基线单源，
    F16b）共用；不支持的写法静默跳过（受控文件，越界即人工介入）。
    """
    out: dict = {}
    stack = [(-1, out)]
    for ln in text.splitlines():
        if not ln.strip() or ln.lstrip().startswith("#"):
            continue
        indent = len(ln) - len(ln.lstrip())
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        m = re.match(r"^(\s*)([\w]+):(?:\s*(.*))?$", ln)
        if not m:
            continue
        key, val = m.group(2), (m.group(3) or "").strip()
        if val == "":
            d = {}
            parent[key] = d
            stack.append((indent, d))
        else:
            if val in ("true", "false"):
                parent[key] = val == "true"
            elif val == "null":
                parent[key] = None
            elif re.match(r"^-?\d+$", val):
                parent[key] = int(val)
            elif re.match(r"^-?\d+\.\d+$", val):
                parent[key] = float(val)
            else:
                parent[key] = val.strip("'\"")
    return out


def parse_chapter(path: str) -> dict:
    """解析 05_chapters/<id>.md：frontmatter（yaml 子集：k: v / 一层嵌套）+ 正文段列表。"""
    text = open(path, encoding="utf-8").read()
    fm = {}
    body = text
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.S)
    if m:
        body = m.group(2)
        cur = None
        for ln in m.group(1).splitlines():
            if not ln.strip() or ln.strip().startswith("#"):
                continue
            mm = re.match(r"^(\s*)([\w]+):\s*(.*)$", ln)
            if not mm:
                continue
            k, v = mm.group(2), mm.group(3).strip().strip("'\"")
            if mm.group(1):
                if cur is not None:
                    fm[cur] = v
                continue
            fm[k] = v
            cur = k
    paragraphs = [strip_marks(p.strip()) for p in re.split(r"\n\s*\n", body) if p.strip()]
    return {"frontmatter": fm, "paragraphs": paragraphs, "title": fm.get("title", ""),
            "number": fm.get("number", ""), "id": fm.get("chapter_id", os.path.basename(path)[:-3])}


def strip_marks(text: str) -> str:
    """剔除 [[F:…]]/[[S:…]] 溯源标注（交付稿不出现标注；[[EV:]] 由导出链另行替换）。"""
    return re.sub(r"\[\[[FSfs]:[^\]]*\]\]", "", text)


def load_chapters_sorted(bid: str, outline: dict) -> list:
    """按 01c 章节顺序装载 05_chapters/*.md（章序以 01c 为准，铁律 2）。"""
    by_id = {}
    ch_dir = os.path.join(bid, "05_chapters")
    for fn in os.listdir(ch_dir):
        if fn.endswith(".md"):
            ch = parse_chapter(os.path.join(ch_dir, fn))
            by_id[ch["id"]] = ch
    out = []
    for node in outline.get("chapters", []):
        cid = node.get("id", "")
        if cid in by_id:
            ch = by_id[cid]
            ch["level"] = node.get("level", 2)
            out.append(ch)
    return out


def persist_failed_nodes(bid: str, meta: dict) -> None:
    """闸门失败时把 failed_nodes 落盘 00_metadata（SKILL §五：记入 failed_nodes 并阻断）。

    metadata.schema 已声明该数组；去重追加，不动其他字段。
    """
    if not meta.get("failed_nodes"):
        return
    p = os.path.join(bid, "00_metadata.json")
    try:
        with open(p, encoding="utf-8") as f:
            cur = json.load(f)
    except (OSError, json.JSONDecodeError):
        return
    nodes = cur.setdefault("failed_nodes", [])
    for n in meta["failed_nodes"]:
        if n not in nodes:
            nodes.append(n)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(cur, f, ensure_ascii=False, indent=1)
