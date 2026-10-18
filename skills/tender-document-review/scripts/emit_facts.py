#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""emit_facts.py — tender-document-review 机读产物序列化便利脚本（v1.2.0 新增，v1.3.1 同步）

把已成表的七类内容（clauses / scoring / system_clues / clarifications / contacts /
blind_format / contract_deviations / coverage_map）序列化为 tender-facts.json，
并按 SKILL.md 第十节做结构校验与序列化后自检。

设计约束（与 SKILL.md 第十节一致）：
- 零外部依赖（纯标准库），任何 Python 3.8+ 环境可跑；
- 脚本只是便利，不构成唯一产出途径：无脚本环境时按 SKILL.md 10.2 手工填写，
  字段含义不变；
- 只报告差异、不自动补猜：校验失败即非零退出并列出差异，绝不替使用者补齐内容；
- 本脚本的结构校验是 assets/tender-facts.schema.json 的最小子集实现
  （type/required/properties/additionalProperties/enum/const/pattern/items）。
  安装了 jsonschema 的环境可改用全量 schema 校验，二者判据一致。

用法：
    python emit_facts.py input.json -o tender-facts.json
    python emit_facts.py input.json -o -                  # 写到 stdout
    python emit_facts.py input.json -o out.json \
        --expected-clauses 42 --expected-scoring 12       # 条目数守恒判据

input.json 形态：接近最终的 JSON（Markdown 成果的机读稿）。可缺省字段：
- clauses[].id 缺省时按出现顺序生成 c-0001、c-0002……（**自填** id 才是稳定主键、排序变化不改；依赖缺省 id 时顺序变化 id 即变，下游请以自填 id 做关联）
- schema_version / contract_schema_version 缺省时按契约常量补 0.4
- source_skill_version 缺省时自动读取 ../SKILL.md frontmatter 的 version
- source_rule_seq 缺省时取 --rule-seq（默认 10，即判词库「规则变更记录」现行历史序号；
  该序号仅追溯快照，不参与任何校验判定）
"""

import argparse
import json
import re
import sys
from pathlib import Path

SCHEMA_VERSION = "0.4"
CONTRACT_SCHEMA_VERSION = "0.4"
DEFAULT_RULE_SEQ = 10
FALLBACK_SKILL_VERSION = "1.4.1"

ROOT_REQUIRED = [
    "schema_version", "contract_schema_version", "source_skill_version", "source_rule_seq",
    "project", "meta", "clauses", "scoring",
    "system_clues", "clarifications", "contacts",
    "blind_format", "contract_deviations", "coverage_map",
]

# ---- 结构校验（schema 最小子集） ----

def _check_type(value, typ):
    if typ == "object":
        return isinstance(value, dict)
    if typ == "array":
        return isinstance(value, list)
    if typ == "string":
        return isinstance(value, str)
    if typ == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if typ == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if typ == "boolean":
        return isinstance(value, bool)
    return True


def validate_against_schema(value, schema, path="$", errors=None):
    """按 assets/tender-facts.schema.json 的最小子集校验。返回错误列表（空=通过）。"""
    if errors is None:
        errors = []
    typ = schema.get("type")
    if typ and not _check_type(value, typ):
        errors.append("%s: 期望类型 %s，实际 %s" % (path, typ, type(value).__name__))
        return errors
    if "const" in schema and value != schema["const"]:
        errors.append("%s: 期望常量 %r，实际 %r" % (path, schema["const"], value))
    if "enum" in schema and value not in schema["enum"]:
        errors.append("%s: 取值 %r 不在允许集合 %r" % (path, value, schema["enum"]))
    if "pattern" in schema and isinstance(value, str):
        if not re.search(schema["pattern"], value):
            errors.append("%s: %r 不匹配模式 %s" % (path, value, schema["pattern"]))
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                errors.append("%s: 缺少必填字段 %r" % (path, key))
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in props:
                    errors.append("%s: 不允许的字段 %r（字段集必须与契约完全一致）" % (path, key))
        for key, sub in props.items():
            if key in value:
                validate_against_schema(value[key], sub, "%s.%s" % (path, key), errors)
    if isinstance(value, list) and "items" in schema:
        for i, item in enumerate(value):
            validate_against_schema(item, schema["items"], "%s[%d]" % (path, i), errors)
    return errors


def load_schema():
    """优先读 assets/tender-facts.schema.json；读不到则用脚本内置最小判据。"""
    schema_path = Path(__file__).resolve().parent.parent / "assets" / "tender-facts.schema.json"
    if schema_path.is_file():
        try:
            return json.loads(schema_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print("警告：schema 读取失败（%s），改用内置最小判据" % exc, file=sys.stderr)
    return _builtin_schema()


def _builtin_schema():
    return {
        "type": "object",
        "required": ROOT_REQUIRED,
        "properties": {
            "schema_version": {"const": SCHEMA_VERSION},
            "contract_schema_version": {"const": CONTRACT_SCHEMA_VERSION},
            "source_skill_version": {"type": "string"},
            "source_rule_seq": {"type": "integer"},
            "project": {"type": "object", "required": ["name", "no", "purchaser"]},
            "meta": {"type": "object", "required": ["doc_source_type", "business_type", "submission_form"]},
            "clauses": {"type": "array"},
            "scoring": {"type": "object", "required": ["items"]},
            "system_clues": {"type": "array"},
            "clarifications": {"type": "array"},
            "contacts": {"type": "object"},
            "blind_format": {"type": "object"},
            "contract_deviations": {"type": "array"},
            "coverage_map": {"type": "array"},
        },
    }


# ---- 序列化后自检（SKILL.md 10.3） ----

def self_checks(doc, expected_clauses=None, expected_scoring=None, expected_total=None):
    """返回 (硬错误, 警告) 两个字符串列表。只报告差异，不自动补齐。"""
    hard, warn = [], []

    if expected_clauses is not None:
        actual = len(doc.get("clauses", []))
        if actual != expected_clauses:
            hard.append("条目数不守恒：clauses=%d，Markdown 七类表行数=%d（差异 %+d）"
                        % (actual, expected_clauses, actual - expected_clauses))
    if expected_scoring is not None:
        actual = len(doc.get("scoring", {}).get("items", []))
        if actual != expected_scoring:
            hard.append("评分点不守恒：scoring.items=%d，上游矩阵行数=%d（差异 %+d）"
                        % (actual, expected_scoring, actual - expected_scoring))

    # ---- D5 评分表分值闭合验算（v0.16 §11.2 阶段 1 验收第 0 条；⓪ SKILL.md「分值闭合验算」） ----
    # 口径：各评分项分值之和须等于文件明示总分（或各权重段分值）。
    # 不等即回原文复核并记录差异；存在「各权重段分值」多口径，故报警告而非硬阻断，
    # 但绝不静默通过——未录入明示总分时同样告警，避免"看起来验过了"。
    items = doc.get("scoring", {}).get("items", [])
    total = 0.0
    non_numeric = []
    for i, it in enumerate(items):
        p = it.get("points")
        if isinstance(p, (int, float)) and not isinstance(p, bool):
            total += float(p)
        else:
            non_numeric.append(i)
    if non_numeric:
        warn.append("分值闭合：scoring.items%s 的 points 非数值或缺失，未计入合计" % (non_numeric,))
    if expected_total is None:
        if items:
            warn.append("分值闭合：未录入「文件明示总分」（--expected-total），当前分值合计 %.6g "
                        "未经闭合验算。按 ⓪ SKILL.md 分值闭合验算要求，须人工从原文录入明示总分后重跑，"
                        "不得静默采用。" % total)
    elif abs(total - expected_total) > 1e-9:
        warn.append("分值闭合差异：评分项分值合计 %.6g ≠ 文件明示总分 %.6g（差异 %+.6g）。"
                    "须回原文复核并记录差异（常见成因：PDF 版面换行折断数值，如「50」读作「5/0」；"
                    "合并单元格漏行；同一评分因素并列两套基准）。若属「各权重段分值」口径不同，"
                    "请改用权重段合计复核并在备注写明依据。" % (total, expected_total, total - expected_total))

    seen = {}
    for i, c in enumerate(doc.get("clauses", [])):
        key = (c.get("category", ""), c.get("local_no", ""))
        if key in seen:
            hard.append("编号不唯一：%r 同时出现在 clauses[%d] 与 clauses[%d]"
                        % (key, seen[key], i))
        seen[key] = i
        if not c.get("page"):
            warn.append("clauses[%d]（%s）：page 为空，建议标 needs_original" % (i, c.get("item", "")))
    return hard, warn


# ---- 主流程 ----

def read_skill_version():
    """从 ../SKILL.md frontmatter 读 version，保 source_skill_version 如实。"""
    skill_md = Path(__file__).resolve().parent.parent / "SKILL.md"
    try:
        head = skill_md.read_text(encoding="utf-8")[:600]
    except OSError:
        return FALLBACK_SKILL_VERSION
    m = re.search(r"^version:\s*(\S+)\s*$", head, re.MULTILINE)
    return m.group(1) if m else FALLBACK_SKILL_VERSION


def fill_defaults(doc, rule_seq):
    doc.setdefault("schema_version", SCHEMA_VERSION)
    doc.setdefault("contract_schema_version", CONTRACT_SCHEMA_VERSION)
    doc.setdefault("source_skill_version", read_skill_version())
    doc.setdefault("source_rule_seq", rule_seq)
    doc.setdefault("project", {"name": "", "no": "", "purchaser": ""})
    # meta 三项是前置判定结论，缺省即报错（缺少必填字段），不得以空串/猜测值补齐——
    # business_type/submission_form 有枚举约束，补空串只会制造"补假值再校验失败"的假动作。
    doc.setdefault("clauses", [])
    scoring = doc.setdefault("scoring", {})
    scoring.setdefault("items", [])
    for key in ("system_clues", "clarifications", "contract_deviations", "coverage_map"):
        doc.setdefault(key, [])
    doc.setdefault("contacts", {})
    doc.setdefault("blind_format", {})
    for i, c in enumerate(doc["clauses"], start=1):
        if not c.get("id"):
            c["id"] = "c-%04d" % i
    return doc


def main(argv=None):
    ap = argparse.ArgumentParser(description="tender-document-review 机读产物序列化（零依赖）")
    ap.add_argument("input", help="接近最终形态的 JSON 输入文件（- 表示 stdin）")
    ap.add_argument("-o", "--output", default="-", help="输出路径，- 表示 stdout（默认 -）")
    ap.add_argument("--expected-clauses", type=int, default=None,
                    help="Markdown 七类表行数（条目数守恒判据）")
    ap.add_argument("--expected-scoring", type=int, default=None,
                    help="上游评分矩阵行数（评分点守恒判据）")
    ap.add_argument("--expected-total", type=float, default=None,
                    help="文件明示总分（分值闭合验算判据，D5 / 计划书 §11.2 阶段 1 验收第 0 条）。"
                         "须人工从原文录入后传入，AI 不得自动解析招标文件后直接采用")
    ap.add_argument("--rule-seq", type=int, default=DEFAULT_RULE_SEQ,
                    help="判词库「规则变更记录」历史序号（默认 %d，仅追溯快照）" % DEFAULT_RULE_SEQ)
    args = ap.parse_args(argv)

    raw = sys.stdin.read() if args.input == "-" else Path(args.input).read_text(encoding="utf-8")
    try:
        doc = json.loads(raw)
    except json.JSONDecodeError as exc:
        print("错误：输入不是合法 JSON：%s" % exc, file=sys.stderr)
        return 1

    doc = fill_defaults(doc, args.rule_seq)

    schema = load_schema()
    errors = validate_against_schema(doc, schema)
    if errors:
        print("错误：结构校验未通过（%d 处）：" % len(errors), file=sys.stderr)
        for e in errors:
            print("  - %s" % e, file=sys.stderr)
        print("按铁律：只报告差异，不自动补猜。请修正输入后重跑。", file=sys.stderr)
        return 1

    hard, warn = self_checks(doc, args.expected_clauses, args.expected_scoring,
                             args.expected_total)
    for w in warn:
        print("警告：%s" % w, file=sys.stderr)
    if hard:
        print("错误：序列化后自检未通过（%d 处）：" % len(hard), file=sys.stderr)
        for e in hard:
            print("  - %s" % e, file=sys.stderr)
        return 2

    out = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
    if args.output == "-":
        sys.stdout.write(out)
    else:
        Path(args.output).write_text(out, encoding="utf-8")
        print("已写出 %s（clauses=%d，scoring.items=%d）"
              % (args.output, len(doc["clauses"]), len(doc["scoring"]["items"])),
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
