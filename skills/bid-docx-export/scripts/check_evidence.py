#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
④ bid-docx-export — 证据检查（M7 检查层，计划书 §8.5.3 五项）
===============================================================
对 03b_evidence-index.json 做装配前检查，输出 06_compliance/evidence-check.md。

五项：
  1. 缺件：03_bid-plan 证据类任务卡（response_form=scan）未被 03b fact_ref
     覆盖 → 列出，废标级（qualification/waste）排前；
  2. 日期一致性：03b valid_to（人录，来自扫描件核对）vs 02_facts.md 同条目
     邻近日期；只比一致性，时效判定归 ②-A（不重判）；
  3. 页数超限：正文字数（CJK 口径）换算 中文约 500 字/页（A4 小四 1.5 倍
     行距，±10% 容差）＋ 证据页数 vs page_limit；
  4. 文件大小超限：--max-mb 或 01b raw_text 自动提取（无来源则信息态跳过）；
  5. 索引自洽：pages↔page_count、order 覆盖恰一次、attach_no 唯一、文件在。

铁律 4：只报事实态，不判定是否废标。
用法：
  python check_evidence.py --bid <bid目录> [--max-mb N]
  rc：0＝无错误项（可有信息态）；1＝有错误项；2＝前置缺失。
"""
import argparse
import json
import math
import os
import re
import sys


def load_json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def cjk_count(text: str) -> int:
    """正文字数：CJK 逐字 + 连续拉丁/数字串计 1，剔除标注与空白。"""
    t = re.sub(r"^---.*?---", "", text, flags=re.S)
    t = re.sub(r"\[\[[A-Za-z]+:[^\]]*\]\]", "", t)
    t = re.sub(r"\s", "", t)
    n = len(re.findall(r"[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]", t))
    n += len(re.findall(r"[A-Za-z0-9]+", t))
    return n


DATE_RE = re.compile(r"(\d{4})[-/年]\s*(\d{1,2})[-/月]\s*(\d{1,2})[日]?")

DATE_RE_CJK = re.compile(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日?")


def norm_date(m) -> str:
    return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"


def kw_of(notes: str) -> str:
    """任务卡 notes 首个分隔段的最长关键词（用于 02_facts.md 定位）。"""
    seg = re.split(r"[+＋;；,，/、\s]", str(notes))
    seg = [s for s in seg if len(s) >= 4]
    return max(seg, key=len) if seg else ""


def check_evidence(bid: str, max_mb=None) -> int:
    p_03b = os.path.join(bid, "03b_evidence-index.json")
    if not os.path.exists(p_03b):
        print("【执行阻断】bid-docx-export 证据检查未执行")
        print(f"原因：{p_03b} 缺失（先运行 scripts/index_evidence.py）")
        return 2
    idx = load_json(p_03b)
    items = idx.get("items", [])
    order = idx.get("order", [])

    plan = {}
    p_plan = os.path.join(bid, "03_bid-plan.json")
    if os.path.exists(p_plan):
        for it in load_json(p_plan).get("items", []):
            if it.get("response_form") == "scan":
                plan[str(it.get("source_ref", ""))] = it
    facts_md = ""
    p_facts = os.path.join(bid, "02_facts.md")
    if os.path.exists(p_facts):
        facts_md = open(p_facts, encoding="utf-8").read()

    errors, infos = [], []

    # ---- 1. 缺件（废标级排前）----
    covered = {str(it.get("fact_ref", "")) for it in items}
    missing = []
    for ref, card in plan.items():
        if ref and ref not in covered:
            missing.append(card)
    missing.sort(key=lambda c: (0 if c.get("source_type") in ("qualification", "waste") else 1, str(c.get("id"))))
    for card in missing:
        tag = "废标级" if card.get("source_type") in ("qualification", "waste") else "一般"
        errors.append(f"缺件[{tag}] {card.get('id')}（{card.get('source_ref')}）：{str(card.get('notes', ''))[:60]}")
    if not missing and plan:
        infos.append(f"缺件：{len(plan)} 条证据类任务卡全部有对应索引（✅）")
    if not plan:
        infos.append("03_bid-plan 无证据类（scan）任务卡，缺件检查跳过")

    # ---- 2. 日期一致性（只比一致性；时效归 ②-A）----
    n_date_checked = 0
    for it in items:
        vt = str(it.get("valid_to", "")).strip()
        if not vt:
            continue
        card = plan.get(str(it.get("fact_ref", "")))
        if not card:
            continue
        kw = kw_of(card.get("notes", ""))
        if not kw or kw not in facts_md:
            continue  # 02_facts 定位不到 → 不比（信息层录入缺失，另由缺件/事实检查覆盖）
        seg = facts_md[max(0, facts_md.index(kw) - 200): facts_md.index(kw) + 300]
        dates = {norm_date(m) for m in DATE_RE.finditer(seg)}
        n_date_checked += 1
        if dates and vt not in dates:
            errors.append(f"日期不一致 {it['id']}：03b.valid_to={vt} vs 02_facts 邻近日期 {sorted(dates)}（以事实库为准，人工核对）")
    infos.append(f"日期一致性：可比对 {n_date_checked} 件（02_facts 无日期的条目不比，时效判定归 ②-A）")
    # D4 闭环：valid_to 全空（铁律 1 生成器留空）→ 明示须人工补填，不得静默 0 项通过
    quals = [it for it in items if str(it.get("type", "")) in ("资质", "证书", "人员")]
    n_empty = sum(1 for it in quals if not str(it.get("valid_to", "")).strip())
    if quals and n_empty == len(quals):
        infos.append(f"⚠️ 资质/证书/人员类 {len(quals)} 件 valid_to 全空（index_evidence 按"
                     "铁律 1 留空）：日期一致性当前未核——须维护人对照扫描件人工补填 03b 后重跑")
    elif quals and n_empty:
        infos.append(f"⚠️ {n_empty}/{len(quals)} 件资质/证书/人员类 valid_to 为空（未填件不参与比对）")

    # ---- 3. 页数超限（正文换算 500 字/页 ±10%）----
    ch_dir = os.path.join(bid, "05_chapters")
    words = 0
    n_ch = 0
    if os.path.isdir(ch_dir):
        for fn in os.listdir(ch_dir):
            if fn.endswith(".md"):
                words += cjk_count(open(os.path.join(ch_dir, fn), encoding="utf-8").read())
                n_ch += 1
    ev_pages = int(idx.get("stats", {}).get("pages_total", 0))
    est_pages = math.ceil(words / 500) if words else 0
    est_upper = math.ceil(words / 450)  # ±10% 容差上限
    limit = None
    sp_path = os.path.join(bid, "07_out", "style-profile.yaml")
    if os.path.exists(sp_path):
        m = re.search(r"^\s*page_limit:\s*(?:'(\d+)'|(\d+)|null)", open(sp_path, encoding='utf-8').read(), re.M)
        if m and (m.group(1) or m.group(2)):
            limit = int(m.group(1) or m.group(2))
    if limit:
        total_est = est_upper + ev_pages
        if total_est > limit:
            errors.append(f"页数超限（估算）：正文约 {est_pages} 页（{words} 字/500 字/页，容差上限 {est_upper}）＋证据 {ev_pages} 页 = {total_est} > 上限 {limit}")
        else:
            infos.append(f"页数：正文约 {est_pages} 页（{words} 字）＋证据 {ev_pages} 页 ≈ {total_est} ≤ 上限 {limit}（✅）")
    else:
        infos.append(f"页数：招标未载明 page_limit（铁律 3：按隐含要求估算并写明依据）；正文约 {est_pages} 页＋证据 {ev_pages} 页")

    # ---- 4. 文件大小超限 ----
    if max_mb is None:
        p_01b = os.path.join(bid, "01b_spec-items.json")
        if os.path.exists(p_01b):
            for it in load_json(p_01b).get("items", []):
                m = re.search(r"(?:文件大小|单个文件|每份文件)[^。]{0,12}?(\d+(?:\.\d+)?)\s*MB", str(it.get("raw_text", "")))
                if m:
                    max_mb = float(m.group(1))
                    break
    if max_mb:
        big = []
        for it in items:
            fp = os.path.join(bid, str(it.get("file", "")))
            if os.path.exists(fp):
                mb = os.path.getsize(fp) / 1048576
                if mb > max_mb:
                    big.append(f"{it['id']} {os.path.basename(fp)} {mb:.1f}MB")
        if big:
            errors.append(f"文件大小超限（>{max_mb}MB）：{'；'.join(big)}")
        else:
            infos.append(f"文件大小：全部 ≤ {max_mb}MB（✅）")
    else:
        infos.append("文件大小：招标未载明上限（电子标平台限制须人工确认）")

    # ---- 5. 索引自洽（断号检查的装配前形态）----
    seen = set()
    for it in items:
        pc = int(it.get("page_count", 0))
        m = re.match(r"^(\d+)(?:-(\d+))?$", str(it.get("pages", "")))
        if not m:
            errors.append(f"索引自洽：{it['id']} pages 字段格式非法 {it.get('pages')!r}")
        else:
            hi = int(m.group(2) or m.group(1))
            if pc != hi - int(m.group(1)) + 1:
                errors.append(f"索引自洽：{it['id']} pages={it.get('pages')} 与 page_count={pc} 不一致")
        if it.get("attach_no") in seen:
            errors.append(f"索引自洽：附件号重复 {it.get('attach_no')}")
        seen.add(it.get("attach_no"))
        fp = os.path.join(bid, str(it.get("file", "")))
        if not os.path.exists(fp):
            errors.append(f"索引自洽：文件缺失 {it.get('file')}")
    if sorted(order) != sorted(it["id"] for it in items):
        errors.append("索引自洽：order 未恰好覆盖全部 items 各一次")
    if not any(e.startswith("索引自洽") for e in errors):
        infos.append("索引自洽：pages/page_count/order/附件号/文件存在性 全部一致（✅）")

    # ---- 输出 06_compliance/evidence-check.md ----
    out_dir = os.path.join(bid, "06_compliance")
    os.makedirs(out_dir, exist_ok=True)
    out_p = os.path.join(out_dir, "evidence-check.md")
    md = ["# 证据检查报告（evidence-check）", "",
          f"> 生成：bid-docx-export check_evidence；条目 {len(items)} 件；只报事实态，不判定是否废标（铁律 4）", ""]
    md.append("## 错误项（G5 前须闭环）" if errors else "## 错误项：无 ✅")
    for e in errors:
        md.append(f"- ❌ {e}")
    md.append("")
    md.append("## 信息态")
    for i in infos:
        md.append(f"- {i}")
    if missing:
        md.append("")
        md.append("### 缺件明细（按废标级优先）")
        for card in missing:
            tag = "废标级" if card.get("source_type") in ("qualification", "waste") else "一般"
            md.append(f"- [{tag}] {card.get('id')}（{card.get('source_ref')}）→ 章节 {card.get('chapter_id')}：{str(card.get('notes', ''))[:70]}")
    with open(out_p, "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")

    print(f"证据检查已输出：{out_p}")
    print(f"错误 {len(errors)} 项 / 信息 {len(infos)} 项" + ("；存在错误项，装配前须闭环" if errors else ""))
    return 1 if errors else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bid", required=True, help="项目 bid 目录")
    ap.add_argument("--max-mb", type=float, default=None, help="单件大小上限 MB（缺省从 01b raw_text 提取）")
    args = ap.parse_args()
    if not os.path.isdir(args.bid):
        print(f"【执行阻断】bid 目录不存在：{args.bid}")
        return 2
    return check_evidence(args.bid, args.max_mb)


if __name__ == "__main__":
    sys.exit(main())


