#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_format_chapters.py — ① bid-response-plan v0.3.0 新增：01c 章节树保真校验
（v0.26.0 重构三态：A 直查 / B 派生重放 / C 常量兜底自比对，见下「用法」）

背景（v0.16 阶段 1 验收记录 #2）：01c 章节树由人工从招标文件「投标文件格式」章
（格式章——在招标文件中的章序因项目而异，不预设固定章号）转抄为 FORMAT_CHAPTERS
常量，实测出两类缺陷——
  ① **连续化重排**：原文档编号不连续（示例市项目技术标为 1、2、7–12，原文档自身跳号），
     转抄时被"顺手拉直"成 1–8，6 处编号与原文对不上；
  ② **括号说明被删**：「项目实施方案（由投标人自行编制）」等 3 处章节名的括号
     说明在转抄时丢失。
章节号对不上是实战致命项（评标按格式废标一票否决），故本脚本把"逐字一致"
从肉眼核对升级为机检：**编号与章节名必须与原文抽取结果逐字一致**。

用法：
    python verify_format_chapters.py --01c <01c_format-outline.json> [--headings <抽取.json>]

三种核对态（v0.26.0 起；Todo 10 第 2 批：FORMAT_CHAPTERS 常量仅兜底，真实章节树
由 bid 根 _headings_*.json 派生）：
  A. 显式 --headings：01c 与人工抽取的原文真值**逐字比对**（原 v0.3.0 逻辑，
     常量兜底 01c 与派生 01c 均可直查——常量与真值不符即实测缺陷暴露口）。
  B. 未给 --headings 且 01c 同目录恰一份 _headings_*.json：**派生重放比对**——
     用该 headings 重跑 derive_chapters，01c.chapters 必须与派生结果逐字段一致
     （防 01c 被手改或派生逻辑漂移；headings 本身即人工真值）。
  C. 无 --headings 且无 _headings_*.json：01c 与 FORMAT_CHAPTERS 冻结常量比对
     ＋显著警告（常量是单项目结构，未抽取真值前不能宣称章节树保真）。

--headings 文件格式（人工从原文格式章抽取，供追溯；派生契约要求 level）：
    {
      "source": "示例发包人示例市100MW风电EPC总承包工程招标文件.docx 投标文件格式（格式章）",
      "headings": [
        {"page": "P5463", "number": "1", "title": "投标函格式", "level": 1}
      ]
    }

判定（退出码 0=一致；1=存在差异，附分类清单；2=读取/契约失败）：
  A 态（直查）：
  - 编号在原文中不存在          → 疑似连续化重排（附原文编号序列，便于对照）
  - 编号存在但章节名不同        → 章节名被改写（含括号说明被删）
  - 原文有而 01c 未收录         → 节点缺失
  - 01c 有而原文无（且编号也不在）→ 多出节点（转抄时自造）
  B 态（重放）：逐位比对 id/number/title/level/page，任一字段漂移即差异。
标题比对按空白归一化（连续空白折叠为一个空格、去首尾）；编号按字符串原样比对。
只报告差异，不自动修改——修正派生源/常量或抽取结果后重跑。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from parse_format_outline import derive_chapters, load_headings


def norm_title(t) -> str:
    """标题空白归一化：连续空白折叠为单空格，去首尾。"""
    return re.sub(r"\s+", " ", str(t)).strip()


def _replay_diff(chapters, derived):
    """B 态逐位比对：01c.chapters vs derive_chapters 重放结果 → 差异清单。"""
    problems = []
    for i in range(max(len(chapters), len(derived))):
        a = chapters[i] if i < len(chapters) else None
        b = derived[i] if i < len(derived) else None
        if a is None:
            problems.append("派生结果第 %d 条在 01c 无对应：n-%s「%s」（01c 缺失或被删）"
                            % (i + 1, b.get("id"), norm_title(b.get("title"))))
            continue
        if b is None:
            problems.append("01c 第 %d 条在派生结果无对应：n-%s「%s」（01c 多出或手改）"
                            % (i + 1, a.get("id"), norm_title(a.get("title"))))
            continue
        if str(a.get("id", "")).strip() != str(b["id"]).strip():
            problems.append("第 %d 条 id 不符：01c=%s vs 派生=%s"
                            % (i + 1, a.get("id"), b["id"]))
        if str(a.get("number", "")).strip() != str(b["number"]).strip():
            problems.append("第 %d 条（%s）编号不符：01c=%r vs 派生=%r"
                            % (i + 1, b["id"], a.get("number"), b["number"]))
        if norm_title(a.get("title")) != norm_title(b["title"]):
            problems.append("第 %d 条（%s）章节名不符：01c「%s」vs 派生「%s」"
                            % (i + 1, b["id"], norm_title(a.get("title")), norm_title(b["title"])))
        if a.get("level") != b["level"]:
            problems.append("第 %d 条（%s）层级不符：01c=%s vs 派生=%s"
                            % (i + 1, b["id"], a.get("level"), b["level"]))
        if str(a.get("page", "")).strip() != str(b["page"]).strip():
            problems.append("第 %d 条（%s）页码不符：01c=%r vs 派生=%r"
                            % (i + 1, b["id"], a.get("page"), b["page"]))
    return problems


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="01c 章节树保真校验（A 直查 / B 派生重放 / C 常量兜底自比对）")
    ap.add_argument("--01c", required=True, help="01c_format-outline.json 路径（同目录自动发现 _headings_*.json）")
    ap.add_argument("--headings", help="格式章标题抽取 JSON 路径（缺省自动发现；显式给 = A 态直查）")
    args = ap.parse_args(argv)

    try:
        outline = json.loads(Path(getattr(args, "01c")).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print("错误：01c 读取/解析失败：%s" % exc, file=sys.stderr)
        return 2

    chapters = outline.get("chapters")
    if not isinstance(chapters, list):
        print("错误：01c 缺 chapters 数组", file=sys.stderr)
        return 2

    # ---------- 核对态路由 ----------
    if args.headings:
        mode = "A"
        try:
            hdoc = json.loads(Path(args.headings).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print("错误：headings 读取/解析失败：%s" % exc, file=sys.stderr)
            return 2
    else:
        bid_dir = str(Path(getattr(args, "01c")).parent)
        hdoc, state, info = load_headings(bid_dir)
        if state == "multi":
            print("错误：01c 同目录存在多份 _headings_*.json，须人工确认后仅保留一份，"
                  "或用 --headings 显式指定：", file=sys.stderr)
            for f in info:
                print("  -", f, file=sys.stderr)
            return 2
        if state == "bad":
            for m in info:
                print("错误：%s" % m, file=sys.stderr)
            return 2
        mode = "B" if state == "one" else "C"

    # ---------- B 态：派生重放比对 ----------
    if mode == "B":
        derived = derive_chapters(hdoc)
        problems = _replay_diff(chapters, derived)
        if problems:
            print("FAIL  01c 章节树与 _headings_*.json 派生结果不一致（%d 处）：" % len(problems))
            for p in problems:
                print("  - %s" % p)
            print("依据：%s" % hdoc.get("source", ""))
            print("按铁律：只报告差异，不自动修改。请重跑 ①（build_bid_plan / parse_format_outline）"
                  "重建 01c，或修正 headings 抽取后重跑。")
            return 1
        print("PASS  01c 章节树 %d 个节点与 _headings_*.json 派生结果逐字段一致（id/编号/章节名/层级/页码）"
              % len(chapters))
        print("      依据：%s" % hdoc.get("source", ""))
        return 0

    # ---------- C 态：常量兜底自比对 ----------
    if mode == "C":
        from parse_format_outline import FORMAT_CHAPTERS
        const_chapters = [{"id": i, "number": n, "title": t, "level": lv, "page": "n/a-无分页"}
                          for (i, n, t, lv) in FORMAT_CHAPTERS]
        problems = _replay_diff(chapters, const_chapters)
        print("⚠️ 未找到 _headings_*.json（01c 同目录）——仅按 FORMAT_CHAPTERS 冻结常量核对。")
        print("   常量是单项目结构（非本项目真实格式章）；请人工抽取 bid 根 _headings_*.json"
              "（含 level）后重跑 ① 派生，方可宣称章节树保真。")
        if problems:
            print("FAIL  01c 章节树与冻结常量不一致（%d 处）：" % len(problems))
            for p in problems:
                print("  - %s" % p)
            return 1
        print("PASS  01c 章节树 %d 个节点与冻结常量一致（兜底态；真实保真须补 headings）" % len(chapters))
        return 0

    # ---------- A 态：直查（原 v0.3.0 逐字比对逻辑） ----------
    headings = hdoc.get("headings")
    if not isinstance(headings, list):
        print("错误：headings 文件缺 headings 数组", file=sys.stderr)
        return 2

    # 原文索引：编号 → [标题...]（同编号多条时逐一比对）
    orig_by_no = {}
    orig_seq = []
    for h in headings:
        no = str(h.get("number", "")).strip()
        title = norm_title(h.get("title", ""))
        orig_by_no.setdefault(no, []).append(title)
        orig_seq.append(no)

    problems = []
    matched = set()   # 已核对的原文 (编号, 标题)
    seen_01c = set()
    for c in chapters:
        no = str(c.get("number", "")).strip()
        title = norm_title(c.get("title", ""))
        if (no, title) in seen_01c:
            problems.append("01c 内节点重复：编号 %s「%s」" % (no, title))
            continue
        seen_01c.add((no, title))
        if no not in orig_by_no:
            problems.append("编号 %r 在原文格式章不存在（疑似连续化重排）" % no)
            continue
        if title not in orig_by_no[no]:
            alts = "／".join("「%s」" % t for t in orig_by_no[no])
            problems.append("编号 %s 章节名不符：01c「%s」vs 原文 %s（章节名被改写或括号说明被删）"
                            % (no, title, alts))
            continue
        matched.add((no, title))

    # 原文有而 01c 未收录
    for h in headings:
        key = (str(h.get("number", "")).strip(), norm_title(h.get("title", "")))
        if key not in matched:
            problems.append("原文节点未收录：编号 %s「%s」（%s）"
                            % (key[0], key[1], h.get("page", "")))

    if problems:
        print("FAIL  01c 章节树与原文格式章标题不一致（%d 处）：" % len(problems))
        for p in problems:
            print("  - %s" % p)
        print("原文编号序列（供对照连续化重排）：%s" % "、".join(orig_seq))
        print("按铁律：只报告差异，不自动修改。若 01c 为常量兜底：常量与本项目原文不符，"
              "请人工抽取 bid 根 _headings_*.json（含 level）后重跑 ① 派生；"
              "若 01c 已是派生：请修正 headings 抽取（编号逐字照录、括号说明保留）后重跑。")
        return 1

    print("PASS  01c 章节树 %d 个节点与原文格式章逐字一致（编号＋章节名）" % len(chapters))
    src = hdoc.get("source", "")
    if src:
        print("      依据：%s" % src)
    return 0


if __name__ == "__main__":
    sys.exit(main())
