#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_format_chapters.py — ① bid-response-plan v0.3.0 新增：01c 章节树保真校验

背景（v0.16 阶段 1 验收记录 #2）：01c 章节树由人工从招标文件第七章「投标文件格式」
转抄为 FORMAT_CHAPTERS 常量，实测出两类缺陷——
  ① **连续化重排**：原文档编号不连续（示例市项目技术标为 1、2、7–12，原文档自身跳号），
     转抄时被"顺手拉直"成 1–8，6 处编号与原文对不上；
  ② **括号说明被删**：「项目实施方案（由投标人自行编制）」等 3 处章节名的括号
     说明在转抄时丢失。
章节号对不上是实战致命项（评标按格式废标一票否决），故本脚本把"逐字一致"
从肉眼核对升级为机检：**编号与章节名必须与原文抽取结果逐字一致**。

用法：
    python verify_format_chapters.py --01c <01c_format-outline.json> \\
        --headings <第七章标题抽取.json>

--headings 文件格式（从原文第七章抽取，供追溯）：
    {
      "source": "示例发包人示例市100MW风电EPC总承包工程招标文件.docx 第七章 投标文件格式",
      "headings": [
        {"page": "P5463", "number": "1", "title": "投标函格式"},
        {"page": "P5707", "number": "二", "title": "技术标"}
      ]
    }

判定（退出码 0=逐字一致；1=存在差异，附分类清单）：
  - 编号在原文中不存在          → 疑似连续化重排（附原文编号序列，便于对照）
  - 编号存在但章节名不同        → 章节名被改写（含括号说明被删）
  - 原文有而 01c 未收录         → 节点缺失
  - 01c 有而原文无（且编号也不在）→ 多出节点（转抄时自造）
标题比对按空白归一化（连续空白折叠为一个空格、去首尾）；编号按字符串原样比对。
只报告差异，不自动修改——修正 FORMAT_CHAPTERS 或抽取结果后重跑。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def norm_title(t) -> str:
    """标题空白归一化：连续空白折叠为单空格，去首尾。"""
    return re.sub(r"\s+", " ", str(t)).strip()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="01c 章节树与原文第七章标题逐字比对（保真机检）")
    ap.add_argument("--01c", required=True, help="01c_format-outline.json 路径")
    ap.add_argument("--headings", required=True, help="第七章标题抽取 JSON 路径")
    args = ap.parse_args(argv)

    try:
        outline = json.loads(Path(getattr(args, "01c")).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print("错误：01c 读取/解析失败：%s" % exc, file=sys.stderr)
        return 2
    try:
        hdoc = json.loads(Path(args.headings).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print("错误：headings 读取/解析失败：%s" % exc, file=sys.stderr)
        return 2

    chapters = outline.get("chapters")
    if not isinstance(chapters, list):
        print("错误：01c 缺 chapters 数组", file=sys.stderr)
        return 2
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
            problems.append("编号 %r 在原文第七章不存在（疑似连续化重排）" % no)
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
        print("FAIL  01c 章节树与原文第七章标题不一致（%d 处）：" % len(problems))
        for p in problems:
            print("  - %s" % p)
        print("原文编号序列（供对照连续化重排）：%s" % "、".join(orig_seq))
        print("按铁律：只报告差异，不自动修改。请修正 FORMAT_CHAPTERS（编号逐字照录、"
              "括号说明保留）或 headings 抽取结果后重跑。")
        return 1

    print("PASS  01c 章节树 %d 个节点与原文第七章逐字一致（编号＋章节名）" % len(chapters))
    src = hdoc.get("source", "")
    if src:
        print("      依据：%s" % src)
    return 0


if __name__ == "__main__":
    sys.exit(main())
