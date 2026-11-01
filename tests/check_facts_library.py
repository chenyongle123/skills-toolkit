#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_facts_library.py —— 企业事实母库（仓库外本地目录）条目契约机检（零依赖，repo/v1.7.33）
================================================================================
定位：母库维护闸门（计划书 v0.21 阶段 6 事实母库部分；企业事实库 README §二/§四 的可执行判据）。
字段契约镜像 facts.schema.yaml（0.1，三技能共用副本）。空库绿（结构先行合法性）；
条目违约 rc=1；W 级提示不抬 rc。母库在仓库外（敏感数据不进 git），--library 必填指路。

检查项（L1–L8，只报告差异、不自动补猜）：
  L1 文件齐全：5 个节 yaml + README.md + 模板.md；无未知文件/目录
  L2 单节结构：每个 yaml 顶层恰一个节键且与文件对应；条目为 `- key: value` 列表
  L3 id：^(?:qual|perf|pers|eq|fin)-\\d{3,}$ 且前缀与文件节匹配；跨五文件全局唯一
  L4 必填字段：节必填字段（facts.schema.yaml 0.1）＋公共三字段 source/updated_at/owner；
     字符串值非空
  L5 母库禁录项目语境字段：is_decisive / evidence_ref（README §二；由快照注入/项目侧填充）
  L6 日期字段：valid_to / completed_on / updated_at 为 YYYY-MM-DD 且为合法日期
  L7 时效：updated_at 超 12 个月 → W 级提示（facts.schema.yaml R2，不抬 rc）
  L8 数值/布尔：amount/revenue 数值、qty 整数且 ≥1、year 整数、owned 为 true/false；
     节外未知字段 → W 级提示（疑似拼写错误或误录项目字段）

不做的事（边界）：
  - 不判事实真伪、不判是否涉密（人工确认职责，README §一/§四）；
  - 不连项目侧 02_facts（两级库快照语义，存在性由 ③ check_facts 写作期核验）；
  - 不查 evidence_ref 指向（母库本就不录该字段）。

用法：
  python tests/check_facts_library.py --library <母库目录>
退出码：0=通过（可有 W 提示）；1=有 L 类错误；2=输入缺失/不可解析。
"""
import argparse
import re
import sys
from datetime import date
from pathlib import Path

# —— 契约常量（镜像 facts.schema.yaml 0.1；改契约须先 bump schema_version）——
SECTION_FILES = {
    "qualifications": "qualifications.yaml",
    "performances": "performances.yaml",
    "personnel": "personnel.yaml",
    "equipment": "equipment.yaml",
    "financials": "financials.yaml",
}
SECTION_FIELDS = {
    "qualifications": ("name", "cert_no", "issuer", "valid_to"),
    "performances": ("project", "amount", "unit", "contract_no", "completed_on"),
    "personnel": ("name", "cert", "cert_no", "valid_to"),
    "equipment": ("name", "model", "qty", "owned"),
    "financials": ("year", "revenue", "unit"),
}
PREFIXES = {
    "qualifications": "qual-", "performances": "perf-", "personnel": "pers-",
    "equipment": "eq-", "financials": "fin-",
}
COMMON_FIELDS = ("source", "updated_at", "owner")
FORBIDDEN_FIELDS = ("is_decisive", "evidence_ref")
DATE_FIELDS = ("valid_to", "completed_on", "updated_at")
NUMERIC_FIELDS = ("amount", "revenue")
INTEGER_FIELDS = {"qty": 1, "year": 1900}  # 字段 → 最小值
BOOL_FIELDS = ("owned",)
ROOT_FILES = {"README.md", "模板.md"} | set(SECTION_FILES.values())
ID_RE = re.compile(r"^(qual|perf|pers|eq|fin)-\d{3,}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TODAY = date.today()


def unquote(v):
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    return v


def parse_library_yaml(path, rel, errors):
    """解析母库 yaml（零依赖子集）：顶层节键 + `- key: value` 列表条目。
    返回 (top_scalars, {节名: [(lineno, 条目dict), ...]})；结构违约记入 errors。"""
    top_scalars = {}
    sections = {}
    cur_section, cur_item = None, None
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        errors.append(f"[L2] {rel}: 不可读（{exc}）")
        return top_scalars, sections
    for lineno, raw in enumerate(text.splitlines(), 1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        if indent == 0 and not stripped.startswith("- "):
            key, _, val = stripped.partition(":")
            key, val = key.strip(), val.strip()
            if val in ("", "[]"):  # `section:` 或 `section: []` 均为空节开头
                cur_section, cur_item = key, None
                sections.setdefault(key, [])
            else:
                top_scalars[key] = (lineno, val)
            continue
        if stripped.startswith("- "):
            if cur_section is None:
                errors.append(f"[L2] {rel}:L{lineno}: 列表条目出现在节键之前")
                continue
            cur_item = {}
            sections[cur_section].append((lineno, cur_item))
            rest = stripped[2:].strip()
            if ":" in rest:
                k, _, v = rest.partition(":")
                cur_item[k.strip()] = (lineno, v.strip())
            continue
        if ":" in stripped and cur_item is not None:
            k, _, v = stripped.partition(":")
            cur_item[k.strip()] = (lineno, v.strip())
        elif cur_item is None:
            errors.append(f"[L2] {rel}:L{lineno}: 缩进行无所属条目：{stripped[:40]}")
    return top_scalars, sections


def check_l1(lib, errors):
    for name in SECTION_FILES.values():
        if not (lib / name).is_file():
            errors.append(f"[L1] 缺节文件：{name}")
    for name in ROOT_FILES:
        if not (lib / name).is_file():
            errors.append(f"[L1] 缺文件：{name}")
    for p in lib.iterdir():
        if p.name not in ROOT_FILES:
            errors.append(f"[L1] 未知{'目录' if p.is_dir() else '文件'}（母库只放五节 yaml＋README＋模板）：{p.name}")


def check_l2(rel, section, top_scalars, sections, errors):
    for key, (lineno, _) in top_scalars.items():
        errors.append(f"[L2] {rel}:L{lineno}: 顶层标量键 {key}（母库 yaml 只允许一个节键）")
    if section not in sections:
        errors.append(f"[L2] {rel}: 缺节键 {section}:")
    for key in sections:
        if key != section:
            errors.append(f"[L2] {rel}: 出现非本文件节键 {key}:（每文件一节）")


def _to_date(v):
    try:
        return date(*map(int, v.split("-")))
    except ValueError:
        return None


def check_entries(rel, section, entries, seen_ids, errors, warns):
    for lineno, entry in entries:
        where = f"{rel}:L{lineno}"
        # L3 id 形态/前缀/唯一
        if "id" not in entry:
            errors.append(f"[L3] {where}: 缺 id")
            continue
        eid = unquote(entry["id"][1])
        if not ID_RE.match(eid):
            errors.append(f"[L3] {where}: id 形态非法：{eid}")
        elif not eid.startswith(PREFIXES[section]):
            errors.append(f"[L3] {where}: id 前缀 {eid.split('-')[0]}- 与文件节 {section} 不匹配")
        if eid in seen_ids:
            errors.append(f"[L3] {where}: id 重复（先见于 {seen_ids[eid]}）：{eid}")
        else:
            seen_ids[eid] = where
        # L4 必填字段
        for k in SECTION_FIELDS[section] + COMMON_FIELDS + ("id",):
            if k not in entry:
                errors.append(f"[L4] {where}: 缺必填字段 {k}")
            elif not unquote(entry[k][1]).strip():
                errors.append(f"[L4] {where}: 字段 {k} 为空")
        # L5 项目语境字段禁录
        for k in FORBIDDEN_FIELDS:
            if k in entry:
                errors.append(f"[L5] {where}: 母库禁录项目语境字段 {k}（快照注入/项目侧填充）")
        known = set(SECTION_FIELDS[section]) | set(COMMON_FIELDS) | {"id"}
        for k, (ln, raw) in entry.items():
            val = unquote(raw)
            # L6 日期
            if k in DATE_FIELDS:
                if not DATE_RE.match(val):
                    errors.append(f"[L6] {where}: 字段 {k} 非 YYYY-MM-DD：{val}")
                elif _to_date(val) is None:
                    errors.append(f"[L6] {where}: 字段 {k} 非法日期：{val}")
            # L7 时效（仅 updated_at）
            if k == "updated_at" and DATE_RE.match(val) and _to_date(val) is not None:
                aged = (TODAY - _to_date(val)).days
                if aged > 365:
                    warns.append(f"[L7] {where}: {eid} updated_at={val} 已 {aged // 30} 个月，引用前须复核（R2）")
            # L8 数值/布尔/未知字段
            if k in NUMERIC_FIELDS:
                try:
                    float(val)
                except ValueError:
                    errors.append(f"[L8] {where}: 字段 {k} 非数值：{val}")
            elif k in INTEGER_FIELDS:
                if not re.fullmatch(r"\d+", val) or int(val) < INTEGER_FIELDS[k]:
                    errors.append(f"[L8] {where}: 字段 {k} 须为 ≥{INTEGER_FIELDS[k]} 的整数：{val}")
            elif k in BOOL_FIELDS:
                if val not in ("true", "false"):
                    errors.append(f"[L8] {where}: 字段 {k} 须为 true/false：{val}")
            if k not in known and k not in FORBIDDEN_FIELDS:
                warns.append(f"[L8] {where}: 未知字段 {k}（拼写/误录？值：{val[:20]}）")


def main():
    ap = argparse.ArgumentParser(description="企业事实母库机检（L1–L8）")
    ap.add_argument("--library", required=True, help="母库目录（仓库外本地路径）")
    args = ap.parse_args()
    lib = Path(args.library).resolve()
    if not lib.is_dir():
        print(f"FAIL: 母库目录不存在：{lib}")
        return 2
    errors, warns = [], []
    check_l1(lib, errors)
    seen_ids = {}
    per_section = {s: 0 for s in SECTION_FILES}
    for section, fname in SECTION_FILES.items():
        rel = fname
        path = lib / fname
        if not path.is_file():
            continue
        top_scalars, sections = parse_library_yaml(path, rel, errors)
        check_l2(rel, section, top_scalars, sections, errors)
        for key, entries in sections.items():
            if key not in SECTION_FIELDS:
                continue  # L2 已报非本文件节键；不按其字段深检
            per_section[key] = per_section.get(key, 0) + len(entries)
            check_entries(rel, key, entries, seen_ids, errors, warns)
    for w in warns:
        print(f"W: {w}")
    print(f"条目分布：{per_section}（共 {sum(per_section.values())} 条）")
    if errors:
        for e in errors:
            print(f"FAIL: {e}")
        print(f"check_facts_library: FAIL（错误 {len(errors)} 项，警告 {len(warns)} 项）")
        return 1
    print(f"check_facts_library: PASS（条目 {sum(per_section.values())} 条，警告 {len(warns)} 项）")
    return 0


if __name__ == "__main__":
    sys.exit(main())

