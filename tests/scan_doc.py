#!/usr/bin/env python3
# SPDX-License-Identifier: CC-BY-NC-4.0
"""scan_doc.py — 计划文档自身一致性自检（零依赖）

用法：python tests/scan_doc.py docs/投标文件Skill建设计划_v0.16.md

检查项：
  D1 标题版本 = 文件名版本
  D2 内部引用 §x[.y] 指向的章/节标题存在
  D3 Markdown 表格列数与表头一致（不查对齐，只查列数）
  D4 文中 ⓪ 技能版本引用与 skills-lock.json 一致
  D5 「待确认」节仍在（不得为实现进度悄悄删掉未决项）
  D6 无未替换占位符（TODO / TBD / ???）
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    if len(sys.argv) < 2:
        print("用法：python tests/scan_doc.py <计划书.md> [--note]")
        print("  --note  记录类文档（验收记录／实测记录）：跳过 D1 版本解析与 D5 待确认节")
        return 2
    note_mode = "--note" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    doc = Path(args[0])
    if not doc.is_absolute():
        doc = ROOT / doc
    text = doc.read_text(encoding="utf-8")
    lines = text.splitlines()
    errors: list[str] = []

    # D1
    m_file = re.search(r"_v(\d+\.\d+)\.md$", doc.name)
    m_title = re.search(r"^#\s+.*?\sv(\d+\.\d+)\s*$", lines[0]) if lines else None
    if note_mode:
        pass  # 记录类文档按日期命名，无版本号，D1 不适用
    elif not m_file or not m_title:
        errors.append("[D1] 无法从文件名或首行标题解析版本")
    elif m_file.group(1) != m_title.group(1):
        errors.append(f"[D1] 文件名 v{m_file.group(1)} ≠ 标题 v{m_title.group(1)}")

    # D2
    headings = set()
    for line in lines:
        m = re.match(r"^#{2,4}\s+(\d+(?:\.\d+){0,2})[\.\s]", line)
        if m:
            num = m.group(1)
            parts = num.split(".")
            for i in range(1, len(parts) + 1):
                headings.add(".".join(parts[:i]))
    # 跨文档引用（"SKILL.md §10.2"、"计划书 §3.7" 一类）不属本文档内部引用，扫描前剔除
    internal_text = re.sub(r"(?:SKILL\.md|计划书)\s*§\d+(?:\.\d+){0,2}", "", text)
    refs = set(re.findall(r"§(\d+(?:\.\d+){0,2})", internal_text))
    # 引用 §x.y.z 只要其任一前缀（§x.y / §x）存在于标题中即视为有效（父节命中即可）
    def ref_ok(r: str) -> bool:
        parts = r.split(".")
        for i in range(len(parts), 0, -1):
            if ".".join(parts[:i]) in headings:
                return True
        return False
    missing = sorted(r for r in refs if not ref_ok(r))
    if missing:
        errors.append(f"[D2] 引用了不存在的章节：{', '.join('§' + r for r in missing)}")

    # D3
    i = 0
    table_no = 0
    while i < len(lines):
        if lines[i].lstrip().startswith("|") and i + 1 < len(lines) and \
           re.match(r"^\s*\|[\s:\-\|]+\|\s*$", lines[i + 1]):
            table_no += 1
            header_cols = lines[i].replace("\\|", "").count("|") - 1
            start = i + 2
            j = start
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                cols = lines[j].replace("\\|", "").count("|") - 1
                if cols != header_cols:
                    errors.append(f"[D3] 第 {j + 1} 行表格列数 {cols} ≠ 表头 {header_cols}（表 #{table_no}）")
                j += 1
            i = j
        else:
            i += 1

    # D4
    lock_path = ROOT / "skills-lock.json"
    if lock_path.exists():
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        ver = lock.get("skills", {}).get("tender-document-review", {}).get("version")
        if ver and f"v{ver}" not in text:
            errors.append(f"[D4] 文中未出现 ⓪ 实读版本 v{ver}（与 skills-lock.json 不一致）")

    # D5
    if not note_mode and "## 13. 待确认" not in text:
        errors.append("[D5] 「待确认」节缺失")

    # D6
    for token in ("TODO", "TBD", "???"):
        if token in text:
            errors.append(f"[D6] 存在未替换占位符：{token}")

    if errors:
        print(f"FAIL  {len(errors)} 项（{doc.name}）")
        for e in errors:
            print("  " + e)
        return 1
    print(f"PASS  {doc.name}：D1–D6 全部通过（表格 {table_no} 张）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
