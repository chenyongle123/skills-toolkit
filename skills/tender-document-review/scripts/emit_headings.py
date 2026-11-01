#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tender-document-review 格式章标题序列化（_headings_*.json，v1.6.0 新增）。

三原则（与 emit_facts.py 同源）：
  1. 零三方依赖（纯标准库，Python 3.8+）；
  2. 只报告差异、不自动补猜——校验失败即非零退出，不替使用者补数据；
  3. 逐字保真——number/title 由人从格式章照录，脚本不重排、不改写、不猜层级。

用法：
  python emit_headings.py input.json -o <项目>/bid/_headings_工程名.json \\
      [--expected-headings N] [--rule-seq 10]

输入：接近最终形态的 JSON（headings 数组＋可选顶层溯源字段）。
输出：补齐溯源顶层字段后的 _headings_*.json（自检通过才写出）。
退出码：0 成功；1 结构校验未通过；2 自检未通过（守恒等硬错误）。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCHEMA_VERSION = "0.1"             # headings 序列化契约版本（首发）
DEFAULT_RULE_SEQ = 10
FALLBACK_SKILL_VERSION = "1.6.1"   # 与 SKILL.md frontmatter 同步 bump
ALLOWED_TOP = ("schema_version", "source_skill_version", "source_rule_seq",
               "source", "headings")


def _is_pos_int(value):
    """正整数判定（bool 不算——True == 1 会误判）。"""
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


def check_headings_contract(doc, errors):
    """结构契约（与 ① parse_format_outline._check_headings 同判据）。"""
    headings = doc.get("headings")
    if not isinstance(headings, list) or not headings:
        errors.append("headings: 须为非空数组（格式章标题清单）")
        return
    levels = []
    for idx, item in enumerate(headings):
        if not isinstance(item, dict):
            errors.append("headings[%d]: 须为对象" % idx)
            continue
        title = item.get("title")
        if not isinstance(title, str) or not title.strip():
            errors.append("headings[%d].title: 须为非空字符串（逐字照录）" % idx)
        if "level" not in item:
            errors.append("headings[%d]: 缺 level（层级语义由人负责，机器不按编号形态猜层级）" % idx)
        elif not _is_pos_int(item["level"]):
            errors.append("headings[%d].level: 须为正整数（最浅层=1），实际 %r" % (idx, item["level"]))
        else:
            levels.append(item["level"])
    if levels and min(levels) != 1:
        errors.append("headings: 最浅层 level 须为 1，实际最小 %d（层级深度须自顶向下归一）" % min(levels))


def validate(doc):
    """结构校验（rc=1 判据）：顶层白名单＋溯源字段类型＋headings 契约。"""
    errors = []
    for key in doc:
        if key not in ALLOWED_TOP:
            errors.append("不允许的顶层字段 %r（允许：%s）" % (key, "、".join(ALLOWED_TOP)))
    if "schema_version" in doc and doc["schema_version"] != SCHEMA_VERSION:
        errors.append("schema_version: 须为 %r，实际 %r" % (SCHEMA_VERSION, doc["schema_version"]))
    if "source_skill_version" in doc and not isinstance(doc["source_skill_version"], str):
        errors.append("source_skill_version: 须为字符串（semver）")
    if "source_rule_seq" in doc and not _is_pos_int(doc["source_rule_seq"]):
        errors.append("source_rule_seq: 须为正整数，实际 %r" % (doc["source_rule_seq"],))
    if "source" in doc and not isinstance(doc["source"], str):
        errors.append("source: 须为字符串（来源说明）")
    check_headings_contract(doc, errors)
    return errors


def read_skill_version():
    """实读本技能 SKILL.md frontmatter 的 version；读不到落 FALLBACK 并告警。"""
    skill_md = Path(__file__).resolve().parent.parent / "SKILL.md"
    try:
        text = skill_md.read_text(encoding="utf-8")[:600]
    except OSError as exc:
        print("[warn] 读取 SKILL.md 失败（%s），source_skill_version 落 FALLBACK=%s"
              % (exc, FALLBACK_SKILL_VERSION), file=sys.stderr)
        return FALLBACK_SKILL_VERSION
    match = re.search(r"^version:\s*(\S+)\s*$", text, re.MULTILINE)
    if not match:
        print("[warn] SKILL.md 前 600 字符未解析到 version，落 FALLBACK=%s" % FALLBACK_SKILL_VERSION, file=sys.stderr)
        return FALLBACK_SKILL_VERSION
    return match.group(1)


def fill_defaults(doc, rule_seq):
    """只补溯源顶层字段（缺省补真值，不补假值；headings 由契约校验兜底报错）。"""
    doc.setdefault("schema_version", SCHEMA_VERSION)
    doc.setdefault("source_skill_version", read_skill_version())
    doc.setdefault("source_rule_seq", rule_seq)
    doc.setdefault("source", "")
    doc.setdefault("headings", [])
    return doc


def self_checks(doc, expected_headings=None):
    """守恒与查重（rc=2 判据）。返回 (硬错误, 警告)。"""
    hard, warn = [], []
    headings = doc.get("headings") or []
    if expected_headings is not None and len(headings) != expected_headings:
        hard.append("条目数不守恒：headings=%d，Markdown 定位表格式章标题行数=%d（差异 %+d）"
                    % (len(headings), expected_headings, len(headings) - expected_headings))

    # 编号查重：组头全表唯一；组内条目同组唯一（组＝两个 level=1 条目之间）。
    # 重复既可能是层级内部重新起编（合法），也可能是漏抄/重抄——告警不阻断。
    head_seen = {}
    child_seen = {}
    group = 0
    for idx, item in enumerate(headings):
        if not isinstance(item, dict):
            continue
        number = str(item.get("number") or "").strip()
        if item.get("level") == 1:
            group += 1
            if number and number in head_seen:
                warn.append("编号查重：组头编号 %r 在 headings[%d] 与 headings[%d] 重复"
                            % (number, head_seen[number], idx))
            elif number:
                head_seen[number] = idx
            continue
        if not number:
            continue
        key = (group, number)
        if key in child_seen:
            warn.append("编号查重：%r 在 headings[%d] 与 headings[%d] 同组重复——可能是层级内部"
                        "重新起编（合法），也可能是漏抄/重抄，须人工分辨"
                        % (number, child_seen[key], idx))
        else:
            child_seen[key] = idx

    for idx, item in enumerate(headings):
        if isinstance(item, dict) and not str(item.get("page") or "").strip():
            warn.append("headings[%d]（%s）：page 为空，建议核对格式章页码或填 n/a-无分页"
                        % (idx, item.get("title", "")))
    return hard, warn


def check_output_unique(output_path):
    """文件唯一性（12.3）：目标目录已有其他 _headings_*.json 时告警。"""
    warns = []
    path = Path(output_path)
    if path.parent.is_dir():
        others = [p.name for p in sorted(path.parent.glob("_headings_*.json"))
                  if p.resolve() != path.resolve()]
        if others:
            warns.append("目标目录已有其他 _headings_*.json（%s）——① 扫描将进入多候选报错态，须只留一份"
                         % "、".join(others))
    return warns


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="tender-document-review（⓪）格式章标题序列化便利脚本（SKILL.md 第十二节）")
    parser.add_argument("input", help="输入 JSON（headings 草稿：{schema_version?, source_skill_version?,"
                                     " source_rule_seq?, source?, headings:[{page?,number?,title,level}]}）")
    parser.add_argument("-o", "--output", required=True,
                        help="输出路径，建议 <项目>/bid/_headings_<工程名>.json")
    parser.add_argument("--expected-headings", type=int, default=None,
                        help="条目数守恒校验值（Markdown 定位表格式章标题行数）；不传则跳过该项")
    parser.add_argument("--rule-seq", type=int, default=DEFAULT_RULE_SEQ,
                        help="source_rule_seq 缺省值（格式章定位判词库的历史序号，默认 %d）" % DEFAULT_RULE_SEQ)
    args = parser.parse_args(argv)

    try:
        with open(args.input, "r", encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError) as exc:
        print("[FAIL] 读取/解析输入 JSON 失败：%s" % exc, file=sys.stderr)
        print("只报告差异，不自动补猜。", file=sys.stderr)
        return 1
    if not isinstance(doc, dict):
        print("[FAIL] 输入 JSON 顶层须为对象，实际 %s" % type(doc).__name__, file=sys.stderr)
        return 1

    errors = validate(doc)
    if errors:
        for msg in errors:
            print("[FAIL] %s" % msg, file=sys.stderr)
        print("共 %d 处结构问题。只报告差异，不自动补猜。" % len(errors), file=sys.stderr)
        return 1

    fill_defaults(doc, args.rule_seq)

    hard, warns = self_checks(doc, args.expected_headings)
    warns.extend(check_output_unique(args.output))
    if hard:
        for msg in hard:
            print("[FAIL] %s" % msg, file=sys.stderr)
        return 2
    for msg in warns:
        print("[warn] %s" % msg, file=sys.stderr)

    text = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
    try:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(text)
    except OSError as exc:
        print("[FAIL] 写出失败：%s" % exc, file=sys.stderr)
        return 2
    print("已写出 %s（headings=%d，source_skill_version=%s，source_rule_seq=%d）"
          % (args.output, len(doc["headings"]), doc["source_skill_version"], doc["source_rule_seq"]),
          file=sys.stderr)
    if warns:
        print("警告 %d 条已列于上，须人工分辨后自行修订（不阻断写出）。" % len(warns), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
