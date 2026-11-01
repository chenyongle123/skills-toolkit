#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""select_facts.py —— 企业事实母库 → 项目 02_facts.yaml 快照（零依赖，repo/v1.7.33）
======================================================================
定位（计划书 v0.21 阶段 6；母库 README §五的可执行工具）：
  从本地母库（仓库外，如 <企业事实母库>）按条目 id / 节名抽条，
  确定性拷贝生成项目 <bid>/02_facts.yaml——五技能链只读这份快照，永不直读母库。

快照语义：
  - 逐字拷贝选中条目（值 token 原样保留，不改写）；
  - is_decisive 统一注入 false（是否废标级依本项目资格条款而定，G2 逐条复核）；
  - evidence_ref 不带（须跑 ④ index_evidence.py 后由人工关联本项目 ev-xxx）；
  - 已存在 02_facts.yaml 拒绝覆盖（保护项目侧人工增补）；--force 先备份再重写。

用法：
  python tools/select_facts.py --library <母库目录> --bid <项目>/bid \
      [--ids qual-001,perf-003] [--sections qualifications,personnel] [--all] [--force]
选择器至少给一个，可组合（并集）。退出码：0=成功；1=选择集/母库问题（不产出文件）；2=IO 错误。

不做的事（边界）：
  - 不改写任何事实值（铁律 1：事实库逐字引用）；
  - 不生成 02_facts.md 人读副本（如需由 agent 生成，须与 yaml 逐字段一致）；
  - 不校验母库健康（入库/维护期跑 tests/check_facts_library.py）。
"""
import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

SECTION_FILES = {
    "qualifications": "qualifications.yaml",
    "performances": "performances.yaml",
    "personnel": "personnel.yaml",
    "equipment": "equipment.yaml",
    "financials": "financials.yaml",
}
# 发射顺序：节字段（facts.schema.yaml 0.1 顺序）→ 公共三字段 → 未知字段原序 → is_decisive
SECTION_FIELDS = {
    "qualifications": ["name", "cert_no", "issuer", "valid_to"],
    "performances": ["project", "amount", "unit", "contract_no", "completed_on"],
    "personnel": ["name", "cert", "cert_no", "valid_to"],
    "equipment": ["name", "model", "qty", "owned"],
    "financials": ["year", "revenue", "unit"],
}
COMMON_FIELDS = ["source", "updated_at", "owner"]
ID_RE = re.compile(r"^(qual|perf|pers|eq|fin)-\d{3,}$")


def parse_library_yaml(path):
    """解析母库 yaml（与 tests/check_facts_library.py 同构的子集解析）。
    返回 (entries, parse_errors)：entries = [{field: raw_token}, ...]（保持文件序）。"""
    entries, errors = [], []
    cur_item = None
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        if indent == 0 and not stripped.startswith("- "):
            cur_item = None          # 开节（含 `section: []` 空节）
            continue
        if stripped.startswith("- "):
            cur_item = {}
            entries.append(cur_item)
            rest = stripped[2:].strip()
            if ":" in rest:
                k, _, v = rest.partition(":")
                cur_item[k.strip()] = v.strip()
            continue
        if cur_item is not None and ":" in stripped:
            k, _, v = stripped.partition(":")
            cur_item[k.strip()] = v.strip()
        else:
            errors.append(f"{path.name}:{lineno}: 无法归属的行：{stripped[:40]}")
    return entries, errors


def load_library(lib_dir):
    """加载母库五文件 → {section: [entry, ...]}；id 索引 → (section, entry)。
    文件缺失/解析错误 → (None, errors)。"""
    lib, index, errors = {}, {}, []
    for section, fname in SECTION_FILES.items():
        path = lib_dir / fname
        if not path.is_file():
            errors.append(f"母库缺文件：{fname}")
            continue
        try:
            entries, perrs = parse_library_yaml(path)
        except (OSError, UnicodeDecodeError) as exc:
            errors.append(f"{fname}: 不可读（{exc}）")
            continue
        errors.extend(perrs)
        lib[section] = entries
        for e in entries:
            eid = _unquote(e.get("id", ""))
            if not eid:
                errors.append(f"{fname}: 存在无 id 条目，跳过其索引")
                continue
            if eid in index:
                errors.append(f"母库 id 重复：{eid}（{index[eid][0]} 与 {section}）")
                continue
            index[eid] = (section, e)
    return (lib, index, errors) if not errors else (None, index, errors)


def _unquote(v):
    v = (v or "").strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    return v


def resolve_selection(lib, index, args):
    """并集解析 --ids/--sections/--all → {section: [entry]}；错误收集。"""
    errors, picked = [], {}
    if args.sections:
        for s in re.split(r"[，,\s]+", args.sections.strip()):
            if not s:
                continue
            if s not in SECTION_FILES:
                errors.append(f"未知节名：{s}（合法：{', '.join(SECTION_FILES)}）")
                continue
            picked.setdefault(s, []).extend(lib[s])
    if args.ids:
        for i in re.split(r"[，,\s]+", args.ids.strip()):
            if not i:
                continue
            if i not in index:
                errors.append(f"母库无此条目 id：{i}")
                continue
            s, e = index[i]
            picked.setdefault(s, []).append(e)
    if args.all:
        for s, entries in lib.items():
            picked.setdefault(s, []).extend(entries)
    # 同节内按 id 去重（--sections 与 --ids 并集可能重复选）
    for s in list(picked):
        seen, uniq = set(), []
        for e in picked[s]:
            eid = _unquote(e.get("id", ""))
            if eid not in seen:
                seen.add(eid)
                uniq.append(e)
        picked[s] = uniq
    if not errors and not picked:
        errors.append("选择集为空：--ids/--sections/--all 至少给一个")
    return picked, errors


def emit_entry(entry, section):
    """单条 → yaml 文本（逐字段按契约顺序，值 token 原样拷贝，is_decisive 置 false）。"""
    lines = [f"  - id: {entry['id']}"] if "id" in entry else ["  - "]
    known = set(SECTION_FIELDS[section]) | set(COMMON_FIELDS) | {"id"}
    for k in SECTION_FIELDS[section]:
        if k in entry:
            lines.append(f"    {k}: {entry[k] if entry[k] != '' else '\"\"'}")
    for k in COMMON_FIELDS:
        if k in entry:
            lines.append(f"    {k}: {entry[k] if entry[k] != '' else '\"\"'}")
    for k in entry:                      # 未知字段原序保留（母库怎么写就怎么拷）
        if k not in known:
            lines.append(f"    {k}: {entry[k] if entry[k] != '' else '\"\"'}")
    lines.append("    is_decisive: false")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="企业事实母库 → 项目 02_facts.yaml 快照")
    ap.add_argument("--library", required=True, help="母库目录（仓库外本地路径）")
    ap.add_argument("--bid", required=True, help="项目 bid 目录（02_facts.yaml 落点）")
    ap.add_argument("--ids", help="条目 id 列表（逗号分隔）")
    ap.add_argument("--sections", help="节名列表（整节抽）")
    ap.add_argument("--all", action="store_true", help="母库全部条目")
    ap.add_argument("--force", action="store_true", help="覆盖已存在的 02_facts.yaml（先备份）")
    args = ap.parse_args()

    lib_dir = Path(args.library)
    bid_dir = Path(args.bid)
    if not lib_dir.is_dir():
        print(f"FAIL: 母库目录不存在：{lib_dir}")
        return 2
    lib, index, errors = load_library(lib_dir)
    if lib is None:
        for e in errors:
            print(f"FAIL: {e}")
        print("select_facts: FAIL（母库不可用，先跑 tests/check_facts_library.py）")
        return 1
    picked, errors = resolve_selection(lib, index, args)
    if errors:
        for e in errors:
            print(f"FAIL: {e}")
        print("select_facts: FAIL（不产出快照）")
        return 1
    total = sum(len(v) for v in picked.values())
    if total == 0:
        print("FAIL: 选择集为空（母库无条目或未选中任何条目），不产出空快照")
        return 1

    out_path = bid_dir / "02_facts.yaml"
    if out_path.exists() and not args.force:
        print(f"FAIL: 已存在 {out_path}（保护项目侧人工增补）；确需重建加 --force")
        return 1
    try:
        bid_dir.mkdir(parents=True, exist_ok=True)
        if out_path.exists() and args.force:
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup = out_path.with_name(f"02_facts.yaml.bak-{stamp}")
            out_path.replace(backup)
            print(f"W: 已备份旧快照 → {backup.name}")
        header = [
            "# 02_facts.yaml —— 企业事实快照（由母库确定性拷贝生成，勿手改事实值）",
            f"# 母库：{lib_dir}｜生成：{datetime.now().strftime('%Y-%m-%d %H:%M')}｜条目 {total} 条",
            "# 复核位①：is_decisive 已全部置 false——G2 事实确认时逐条按本项目资格条款改判",
            "# 复核位②：evidence_ref 未带——跑 ④ index_evidence.py 后人工关联本项目 ev-xxx",
        ]
        parts = ["\n".join(header), 'schema_version: "0.1"']
        for section in SECTION_FILES:                       # 固定节序，只出非空节
            if picked.get(section):
                body = "\n".join(emit_entry(e, section) for e in picked[section])
                parts.append(f"{section}:\n{body}")
        out_path.write_text("\n\n".join(parts) + "\n", encoding="utf-8")
    except OSError as exc:
        print(f"FAIL: 写出失败：{exc}")
        return 2

    for s in SECTION_FILES:
        if picked.get(s):
            ids = ", ".join(_unquote(e["id"]) for e in picked[s] if "id" in e)
            print(f"  {s}: {len(picked[s])} 条（{ids}）")
    print(f"select_facts: PASS（共 {total} 条 → {out_path}；两复核位见文件头注释）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
