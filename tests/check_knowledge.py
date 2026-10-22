#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_knowledge.py —— 素材母库（knowledge/）条目契约机检（零依赖，repo/v1.7.32）
======================================================================
定位：母库维护闸门（计划书 v0.20 阶段 6 结构部分；知识库 README §四/§六/§七/§八 的可执行判据）。
空库绿（结构先行合法性）；条目违约 rc=1；W 级提示不抬 rc。

检查项（K1–K9，只报告差异、不自动补猜）：
  K1 目录结构：5 类别目录在位、各附 README.md；根级无未知文件/目录
  K2 词表：tags词表.md 存在且可解析（≥4 维度、≥20 标签）
  K3 frontmatter：③ 契约五字段（id/title/use_when/tags/verifiable_facts）
     ＋母库附加三字段（source/updated_at/owner）齐全；title/use_when/source/owner 非空
  K4 id：^kn-\\d{3,}$ 且全库唯一（只增不回收，重复即报）
  K5 tags：≥1 个且全部命中受控词表（词表外红灯）
  K6 updated_at：YYYY-MM-DD；超 12 个月 → W 级提示（R8，不抬 rc）
  K7 verifiable_facts：id 形态 ^(?:qual|perf|pers|eq|fin)-\\d{3,}$（仅格式，
     母库不连项目侧 02_facts，存在性由 ③ check_facts 在写作期核验）
  K8 正文：frontmatter 之后有正文；正文 <50 字 → W 级提示（疑似占位空壳）
  K9 文件名：kn-XXX_标题.md 前缀与 frontmatter id 一致

不做的事（边界）：
  - 不判素材内容质量、不判是否涉密（人工复核职责，见 knowledge/README §六）；
  - 不扫正文里的可核查事实（漏检风险已知，机检抽检＋人工双保险中的"抽检"指本脚本
    的结构面——内容面靠人工，README §六已声明）。

用法：
  python tests/check_knowledge.py [knowledge目录]   # 缺省 = 仓库根 knowledge/
退出码：0=通过（可有 W 提示）；1=有 K 类错误；2=输入缺失/不可解析。
"""
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KNOW = ROOT / "knowledge"
CATEGORIES = ("01-同类工程经验", "02-专项工艺", "03-保证措施", "04-服务承诺", "05-技术路线")
ROOT_FILES = {"README.md", "tags词表.md", "素材条目模板.md"}
CONTRACT_FIELDS = ("id", "title", "use_when", "tags", "verifiable_facts")
EXTRA_FIELDS = ("source", "updated_at", "owner")
ID_RE = re.compile(r"^kn-\d{3,}$")
FACT_RE = re.compile(r"^(?:qual|perf|pers|eq|fin)-\d{3,}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TODAY = date.today()


def parse_frontmatter(text):
    """拆 (frontmatter dict, 正文)。行内列表 [a, b]；去引号；块状列表不支持（README §四）。"""
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.S)
    if not m:
        return None, text
    fm = {}
    for line in m.group(1).splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        mm = re.match(r"^(\w+):\s*(.*)$", s)
        if not mm:
            continue
        k, v = mm.group(1), mm.group(2).strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
            v = v[1:-1]
        if v.startswith("[") and v.endswith("]"):
            inner = v[1:-1].strip()
            v = [x.strip().strip("\"'") for x in inner.split(",")] if inner else []
        fm[k] = v
    return fm, m.group(2)


def parse_vocab(path):
    """词表 = markdown 表格行（| 标签 | 维度 | 说明 |），跳表头与分隔行。"""
    tags = {}
    dims = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\|\s*([^|\s][^|]*?)\s*\|\s*([^|\s][^|]*?)\s*\|", line)
        if not m:
            continue
        tag, dim = m.group(1), m.group(2)
        if set(tag) <= set("-: ") or tag == "标签":
            continue
        if set(dim) <= set("-: ") or dim == "维度":
            continue
        tags.setdefault(tag, dim)
        dims.add(dim)
    return tags, dims


def check_k1(know, errors):
    for cat in CATEGORIES:
        d = know / cat
        if not d.is_dir():
            errors.append(f"[K1] 缺类别目录：{cat}/")
        elif not (d / "README.md").is_file():
            errors.append(f"[K1] {cat}/ 缺类别说明 README.md")
    for p in know.iterdir():
        if p.is_file() and p.name not in ROOT_FILES:
            errors.append(f"[K1] 根级未知文件（条目必须入类别目录）：{p.name}")
        if p.is_dir() and p.name not in CATEGORIES:
            errors.append(f"[K1] 根级未知目录：{p.name}/")


def check_entries(know, vocab, errors, warns):
    seen_ids = {}
    per_cat = {c: 0 for c in CATEGORIES}
    for cat in CATEGORIES:
        for f in sorted((know / cat).glob("*.md")):
            if f.name == "README.md":
                continue
            per_cat[cat] += 1
            rel = f"{cat}/{f.name}"
            try:
                text = f.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                errors.append(f"[K3] {rel}: 不可读（{exc}）")
                continue
            fm, body = parse_frontmatter(text)
            if fm is None:
                errors.append(f"[K3] {rel}: 缺 frontmatter（--- 分隔）")
                continue
            for k in CONTRACT_FIELDS + EXTRA_FIELDS:
                if k not in fm:
                    errors.append(f"[K3] {rel}: 缺字段 {k}")
            for k in ("id", "title", "use_when", "source", "owner"):
                v = fm.get(k)
                if isinstance(v, str) and not v.strip():
                    errors.append(f"[K3] {rel}: 字段 {k} 为空")
            kid = fm.get("id")
            if isinstance(kid, str):
                if not ID_RE.match(kid):
                    errors.append(f"[K4] {rel}: id 非法（^kn-\\d{{3,}}$）：{kid}")
                if kid in seen_ids:
                    errors.append(f"[K4] {rel}: id 重复（先见于 {seen_ids[kid]}）：{kid}")
                else:
                    seen_ids[kid] = rel
                prefix = f.name.split("_", 1)[0].split(".", 1)[0]
                if prefix != kid:
                    errors.append(f"[K9] {rel}: 文件名前缀 {prefix} ≠ frontmatter id {kid}")
            tags = fm.get("tags")
            if isinstance(tags, list):
                if not tags:
                    errors.append(f"[K5] {rel}: tags 为空（契约要求 ≥1）")
                for t in tags:
                    if t not in vocab:
                        errors.append(f"[K5] {rel}: 词表外标签：{t}")
                if len(tags) > 8:
                    warns.append(f"[K5] {rel}: tags {len(tags)} 个偏多（建议四维各 1–2）")
            elif tags is not None and not isinstance(tags, list):
                errors.append(f"[K3] {rel}: tags 须为行内列表 [a, b]（块状列表不支持）")
            vts = fm.get("verifiable_facts")
            if isinstance(vts, list):
                for vid in vts:
                    if not FACT_RE.match(str(vid)):
                        errors.append(f"[K7] {rel}: 事实 id 形态非法：{vid}")
            ua = fm.get("updated_at")
            if isinstance(ua, str) and DATE_RE.match(ua):
                try:
                    aged = (TODAY - date(*map(int, ua.split("-")))).days
                    if aged > 365:
                        warns.append(f"[K6] {rel}: updated_at={ua} 已 {aged//30} 个月，引用前须复核（R8）")
                except ValueError:
                    errors.append(f"[K6] {rel}: updated_at 非法日期：{ua}")
            elif "updated_at" in fm:
                errors.append(f"[K6] {rel}: updated_at 非 YYYY-MM-DD：{ua}")
            if body is not None and len(body.strip()) < 50:
                warns.append(f"[K8] {rel}: 正文不足 50 字（疑似占位空壳）")
    return per_cat


def main():
    know = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else KNOW
    if not know.is_dir():
        print(f"FAIL: knowledge 目录不存在：{know}")
        return 2
    errors, warns = [], []
    check_k1(know, errors)
    vocab_path = know / "tags词表.md"
    vocab, dims = (None, set())
    if not vocab_path.is_file():
        errors.append("[K2] 缺 tags词表.md")
    else:
        vocab, dims = parse_vocab(vocab_path)
        if len(vocab) < 20 or len(dims) < 4:
            errors.append(f"[K2] 词表解析异常（标签 {len(vocab)} 个/维度 {len(dims)} 个）")
    per_cat = check_entries(know, vocab or {}, errors, warns)
    total = sum(per_cat.values())
    for w in warns:
        print(f"W: {w}")
    print(f"条目分布：{ {c: n for c, n in per_cat.items()} }（共 {total} 条）")
    if errors:
        for e in errors:
            print(f"FAIL: {e}")
        print(f"check_knowledge: FAIL（错误 {len(errors)} 项，警告 {len(warns)} 项）")
        return 1
    print(f"check_knowledge: PASS（条目 {total} 条，警告 {len(warns)} 项）")
    return 0


if __name__ == "__main__":
    sys.exit(main())

