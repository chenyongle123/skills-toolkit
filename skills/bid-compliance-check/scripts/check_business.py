#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
② bid-compliance-check — M8 商务表专项检查（check_business.py）
==============================================================
SPDX-License-Identifier: CC-BY-NC-4.0

读取 03c_business-forms.json（M8 框架）+ 01c_format-outline.json（章节解析）+ 03_bid-plan.json（可选，交叉引用），
对 M8 商务表框架做专项检查。落点：计划书 §11.2 验收第 9 条、§4.3 D 类、§5 目录树。

检查项（B1–B7）：
  B1 零金额（★阻断级）：03c 业务语义字段不得含任何金额数字（铁律 1：AI 不预填不测算）
  B2 required_fields 齐备：每张表必填字段非空
  B3 seal 齐备：每张表签章要求非空（「未载明」可接受但标注）
  B4 chapter_id 可解析：每张表 chapter_id 须能解析到 01c 章节
  B5 consistency_rules 齐备：至少覆盖「大写=小写 / 分项合计=总价 / 保证金」三条
  B6 —— 不在此脚本：表格↔任务卡一一对应属 D 类，由 check_compliance.py 唯一实现，此处不复制
  B7 表格数声明：03c 表数 = 招标商务格式章要求的表数 —— ② 不读招标原文，**不可独立机检**，
     如实标注「以 ① 抽取声明为准」，不得无源断言

边界：只报事实态，不填金额、不算价、不改写 03c（M8「① 出框架 / ② 查 / ④ 装订，均不填价」）。
②-B（--mode B，人工填写后）：08_business/ 成稿的行内大小写金额等值核对 +
分项合计=总价人工核对声明（表格结构无通用机检口径，不得无源断言——B2/B5 已查
字段与规则覆盖，数值合计归人工）。

运行要求：Python ≥ 3.12（与 check_compliance.py 同基线）。
用法：
  python check_business.py --bid <项目/bid目录> [--mode A]
退出码：0 无阻断；1 存在阻断级（B1 检出金额）。
"""
import argparse
import json
import os
import re
import sys

# ---------------- 金额检测 ----------------
# 强特征：命中即判定为金额（阻断级）。用于全部业务语义字段 + seal。
STRONG_MONEY_PATTERNS = [
    (re.compile(r"[¥￥$€]\s*[\d,]+(?:\.\d+)?"), "货币符号金额"),
    (re.compile(r"[\d,]+(?:\.\d+)?\s*(?:元|万元|亿元|万圆|亿圆|万元整)"), "数字+金额单位"),
    (re.compile(r"\d{1,3}(?:,\d{3})+"), "千分位金额"),
    # 中文大写金额：大写数字开头 + 进位/数字 + 可选万/亿 + 必有「元/圆」+ 可选「整」
    # 要求必有「元/圆」，避免把「贰级资质」「叁级」等非金额语境误判为金额。
    (re.compile(r"[壹贰叁肆伍陆柒捌玖][拾佰仟壹贰叁肆伍陆柒捌玖]*[万亿]?[元圆][整]?"),
     "中文大写金额"),
]
# 弱特征：疑似金额，仅提示人工确认（不阻断）。不用于 seal（seal 允许条款号引用）。
WEAK_MONEY_PATTERNS = [
    (re.compile(r"\d+\.\d{2}(?![\d.])"), "两位小数（疑似金额）"),
    (re.compile(r"\d{5,}"), "连续 5 位以上数字（疑似金额）"),
]

# 业务语义字段：金额零容忍（强+弱皆查）
SEMANTIC_FIELDS = ("name", "required_fields", "consistency_rules")
# 结构/位置字段：豁免（含数字合法，如页码 P45、章节 n-1000、份数 5、路径 08_business/bf-01…）
EXEMPT_FIELDS = ("id", "tender_page", "chapter_id", "copies", "filled_file",
                 "schema_version", "status")
# seal：允许条款号引用（如「按前附表3.4.1」「按报价要求1.1-1.17」），只查强特征
SEAL_FIELD = "seal"

# consistency_rules 三条硬性规则（商务表格抽取规则 §三.4）
RULE_KEYWORDS = {
    "大写=小写": ["大写", "小写"],
    "分项合计=总价": ["合计", "总价"],
    "保证金一致": ["保证金"],
}


def load(p):
    if not os.path.exists(p):
        raise FileNotFoundError(f"M8 检查缺少输入：{p}")
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def load_text(p):
    try:
        return open(p, encoding="utf-8").read()
    except FileNotFoundError:
        return ""


def scan_money(text, strong_only=False):
    """扫描一段文本中的金额特征。返回 [(类型, 命中样例), ...]"""
    hits = []
    for pat, desc in STRONG_MONEY_PATTERNS:
        m = pat.search(text)
        if m:
            hits.append((desc, m.group(0)))
    if not strong_only:
        for pat, desc in WEAK_MONEY_PATTERNS:
            m = pat.search(text)
            if m:
                hits.append((desc, m.group(0)))
    return hits


def check_zero_amount(bus):
    """B1 零金额（阻断级）。只扫业务语义字段 + seal(仅强特征)，豁免结构/位置字段。"""
    findings = []   # 阻断级（强特征）
    warnings = []   # 提示级（弱特征）
    forms = bus.get("forms", [])

    for f in forms:
        fid = f.get("id", "?")
        # 业务语义字段：强+弱
        for field in SEMANTIC_FIELDS:
            val = f.get(field)
            if field == "required_fields":
                for i, item in enumerate(val or []):
                    for desc, sample in scan_money(str(item)):
                        rec = (fid, f"required_fields[{i}]", desc, sample, str(item))
                        (findings if desc in ("货币符号金额", "数字+金额单位",
                                              "千分位金额", "中文大写金额") else warnings).append(rec)
            else:
                for desc, sample in scan_money(str(val or "")):
                    rec = (fid, field, desc, sample, str(val))
                    (findings if desc in ("货币符号金额", "数字+金额单位",
                                          "千分位金额", "中文大写金额") else warnings).append(rec)
        # seal：只查强特征（条款号引用合法）
        for desc, sample in scan_money(str(f.get(SEAL_FIELD) or ""), strong_only=True):
            findings.append((fid, "seal", desc, sample, str(f.get(SEAL_FIELD))))

    # consistency_rules（顶层）：强+弱
    for i, rule in enumerate(bus.get("consistency_rules", [])):
        for desc, sample in scan_money(str(rule)):
            rec = ("consistency_rules", f"[{i}]", desc, sample, str(rule))
            (findings if desc in ("货币符号金额", "数字+金额单位",
                                  "千分位金额", "中文大写金额") else warnings).append(rec)
    return findings, warnings


def check_required_fields(bus):
    """B2 required_fields 齐备"""
    missing = []
    for f in bus.get("forms", []):
        rf = f.get("required_fields")
        if not rf or (isinstance(rf, list) and not any(str(x).strip() for x in rf)):
            missing.append(f.get("id", "?"))
    return missing


def check_seal(bus):
    """B3 seal 齐备；「未载明」合法但标注"""
    missing, undeclared = [], []
    for f in bus.get("forms", []):
        seal = (f.get("seal") or "").strip()
        if not seal:
            missing.append(f.get("id", "?"))
        elif seal == "未载明":
            undeclared.append(f.get("id", "?"))
    return missing, undeclared


def check_chapter_id(bus, fmt):
    """B4 chapter_id 能否解析到 01c 章节"""
    if fmt is None:
        return None, [], "01c_format-outline.json 缺失，章节解析不可校验"
    chapter_ids = {c.get("id") for c in fmt.get("chapters", [])}
    unresolved = [f.get("id", "?") for f in bus.get("forms", [])
                  if f.get("chapter_id") not in chapter_ids]
    return chapter_ids, unresolved, ""


def check_consistency_rules(bus):
    """B5 consistency_rules 三条硬性规则覆盖情况"""
    rules_text = " ".join(str(r) for r in bus.get("consistency_rules", []))
    covered, missing = [], []
    for name, kws in RULE_KEYWORDS.items():
        if all(k in rules_text for k in kws):
            covered.append(name)
        else:
            missing.append(name)
    return covered, missing


def mode_b_business(bid):
    """②-B 商务表成稿检查（C8 实装）：08_business/ 人工填写文件 × 行内大小写金额等值核对。

    口径：同一行内同时出现中文大写金额与数字金额（商务表「大写：捌拾万元整 / 小写：
    ¥800,000.00」形态）→ 归一比对；行内两集合无交集值即不等值（错误级）。
    分项合计=总价：表格结构无通用机检口径，明确声明人工核对（不得无源断言）。
    rc：0 无不等值；1 检出行内大小写不等值；2 前置缺失（08_business/ 空）。
    """
    biz_dir = os.path.join(bid, "08_business")
    if not os.path.isdir(biz_dir):
        print("【执行阻断】bid-compliance-check（②-B 商务表）未执行")
        print(f"原因：{biz_dir} 不存在（商务表人工填写目录）")
        return 2
    files = sorted(fn for fn in os.listdir(biz_dir)
                   if os.path.splitext(fn)[1].lower() in (".md", ".txt", ".csv"))
    if not files:
        print("【执行阻断】bid-compliance-check（②-B 商务表）未执行")
        print(f"原因：{biz_dir} 无 .md/.txt/.csv 人工填写文件")
        return 2

    n_pairs = n_bad = 0
    print(f"②-B 商务表成稿检查：{len(files)} 个文件")
    for fn in files:
        path = os.path.join(biz_dir, fn)
        for i, ln in enumerate(open(path, encoding="utf-8").read().splitlines(), 1):
            ups = [(m.group(0), parse_cn_amount(m.group(0))) for m in CN_AMT_RE.finditer(ln)]
            lows = [(m.group(0), amount_to_yuan_b(m.group(0))) for m in NUM_AMT_RE.finditer(ln)]
            ups = [(t, v) for t, v in ups if v is not None]
            lows = [(t, v) for t, v in lows if v is not None]
            if not ups or not lows:
                continue
            n_pairs += 1
            up_vals = {round(v, 2) for _, v in ups}
            low_vals = {round(v, 2) for _, v in lows}
            if up_vals & low_vals:
                continue
            n_bad += 1
            print(f"  ❌ {fn} L{i}：行内大小写不等值——大写 {[t for t, _ in ups]} vs "
                  f"小写 {[t for t, _ in lows]}（归一 {[sorted(up_vals)]} vs {[sorted(low_vals)]}）")
    print(f"行内大小写金额核对：{n_pairs} 对，不等值 {n_bad} 对" + (" ❌" if n_bad else " ✅"))
    if n_pairs == 0:
        print("ℹ️ 未检出「大写+小写」同现行（商务表未双写或金额未填；填写完整性另见 --mode A B1/B2）")
    print("分项合计=总价：表格结构无通用机检口径，须人工核对（B5 已核 consistency_rules 规则覆盖；"
          "铁律 1：AI 不测算价格）")
    return 1 if n_bad else 0


# 中文大写金额归一（与 check_consistency.py 同口径；独立分发各自实现，改须两处同步）
_CN_NORM_B = str.maketrans("壹贰叁肆伍陆柒捌玖拾佰仟", "一二三四五六七八九十百千")
_CN_DIGIT_B = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
_CN_UNIT_B = {"十": 10, "百": 100, "千": 1000}
CN_AMT_RE = re.compile(r"[零壹贰叁肆伍陆柒捌玖拾佰仟]+(?:[万亿][零壹贰叁肆伍陆柒捌玖拾佰仟]*)*[元圆][整]?|"
                       r"[零壹贰叁肆伍陆柒捌玖拾佰仟万亿]+[元圆][整]?")
NUM_AMT_RE = re.compile(r"[¥￥]\s*[\d,]+(?:\.\d+)?|[\d,]+(?:\.\d+)?\s*(?:亿元|万元|元)")


def _cn_section_b(seg):
    if not seg:
        return 0
    total, num = 0, 0
    for ch in seg:
        if ch in _CN_DIGIT_B:
            num = _CN_DIGIT_B[ch]
        elif ch in _CN_UNIT_B:
            total += (num or 1) * _CN_UNIT_B[ch]
            num = 0
        else:
            return None
    return total + num


def parse_cn_amount(s):
    """中文金额串 → 元（float）；失败返 None（同 check_consistency.parse_cn_amount）。"""
    t = re.sub(r"人民币|圆|元|整|零", "", s).translate(_CN_NORM_B)
    if not t or not re.fullmatch(r"[一二三四五六七八九十百千万亿]+", t):
        return None
    parts = re.split(r"([万亿])", t)
    yuan, m, i = 0.0, 1, len(parts) - 1
    seg = _cn_section_b(parts[i])
    if seg is None:
        return None
    yuan += seg
    i -= 1
    while i >= 1:
        seg = _cn_section_b(parts[i - 1])
        if seg is None:
            return None
        m *= {"万": 1e4, "亿": 1e8}[parts[i]]
        yuan += seg * m
        i -= 2
    return yuan if yuan else None


def amount_to_yuan_b(raw):
    """数字金额 → 元；失败返 None（同 check_consistency.amount_to_yuan 口径）。"""
    s = re.sub(r"\s+", "", raw)
    if re.fullmatch(r"[¥￥][\d,]+(?:\.\d+)?", s):
        return float(s[1:].replace(",", ""))
    m = re.fullmatch(r"([\d,]+(?:\.\d+)?)(亿元|万元|元)", s)
    if m:
        return float(m.group(1).replace(",", "")) * {"亿元": 1e8, "万元": 1e4, "元": 1}[m.group(2)]
    return None


def gate_a(bid):
    """②-A M8 入口闸门（形态对齐 ④ `_common.gate()` / `check_compliance.mode_b`）：
    缺一即拒，rc=2，零产物。唯一必需前置＝`03c_business-forms.json`（① 产出）。

    注意：本脚本不验 stage——它是 ②-A 的**子检查**，stage 由 `check_compliance --mode A`
    的 `gate_a()` 统一把关，避免同一关卡两处判定的口径漂移。
    """
    banner = "【执行阻断】bid-compliance-check · M8 商务表检查（②-A）未执行"
    p03c = os.path.join(bid, "03c_business-forms.json")
    if not os.path.exists(p03c):
        return 2, [banner,
                   "原因：缺 03c_business-forms.json（商务表框架，① bid-response-plan 产出）",
                   "处置：请先执行 ① bid-response-plan（python skills/bid-response-plan/scripts/build_bid_plan.py --bid <项目>/bid）后重试"]
    try:
        with open(p03c, encoding="utf-8") as f:
            json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return 2, [banner,
                   f"原因：03c_business-forms.json 不可解析：{e}",
                   "处置：重跑 ① bid-response-plan 修复该产物后重试"]
    return 0, []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bid", required=True, help="项目 bid 目录")
    ap.add_argument("--mode", choices=["A", "B"], default="A")
    args = ap.parse_args()
    bid = args.bid

    if args.mode == "B":
        return mode_b_business(bid)

    rc, msgs = gate_a(bid)
    for m in msgs:
        print(m)
    if rc != 0:
        return rc  # 缺件：阻断，零产物（此时不得创建 06_compliance/）

    p03c = os.path.join(bid, "03c_business-forms.json")
    p01c = os.path.join(bid, "01c_format-outline.json")
    p03 = os.path.join(bid, "03_bid-plan.json")
    out_dir = os.path.join(bid, "06_compliance")
    os.makedirs(out_dir, exist_ok=True)

    bus = load(p03c)
    fmt = load(p01c) if os.path.exists(p01c) else None

    forms = bus.get("forms", [])
    total = len(forms)

    # ---- B1 零金额（阻断级）----
    findings, warnings = check_zero_amount(bus)
    # ---- B2/B3 ----
    rf_missing = check_required_fields(bus)
    seal_missing, seal_undeclared = check_seal(bus)
    # ---- B4 ----
    chapter_ids, unresolved, chapter_note = check_chapter_id(bus, fmt)
    # ---- B5 ----
    rules_covered, rules_missing = check_consistency_rules(bus)

    blocked = bool(findings)
    verdict = "❌ 阻断（检出金额数字，须回 ① 清除后重跑）" if blocked else "✅ 通过（零金额）"

    # ---------------- 输出 markdown ----------------
    md = []
    md.append("# 商务表检查（M8 / B 类）\n")
    md.append(f"- 检查对象：`03c_business-forms.json`（{total} 张表）")
    md.append(f"- **B1 零金额：{verdict}**\n")

    if findings:
        md.append("### B1 阻断项（业务语义字段检出金额）\n")
        md.append("| 表ID | 字段 | 类型 | 命中 | 原文 |")
        md.append("|---|---|---|---|---|")
        for fid, field, desc, sample, raw in findings:
            md.append(f"| {fid} | {field} | {desc} | `{sample}` | {raw[:40]} |")
        md.append("\n> 铁律 1 / M8：框架不得含任何金额数字，报价由人工填写。"
                  "请回 ① 清除上述字段中的金额后重跑。\n")
    else:
        md.append("- 业务语义字段（`name` / `required_fields` / `consistency_rules`）"
                  "及 `seal` 均未检出金额数字。\n")
    if warnings:
        md.append("### B1 提示项（疑似金额，人工确认）\n")
        md.append("| 表ID | 字段 | 类型 | 命中 | 原文 |")
        md.append("|---|---|---|---|---|")
        for fid, field, desc, sample, raw in warnings:
            md.append(f"| {fid} | {field} | {desc} | `{sample}` | {raw[:40]} |")
        md.append("")

    md.append("## B2 必填字段齐备\n")
    md.append(f"- 缺失 required_fields 的表：{', '.join(rf_missing) if rf_missing else '无'}")
    md.append("## B3 签章要求齐备\n")
    md.append(f"- 缺失 seal 的表：{', '.join(seal_missing) if seal_missing else '无'}")
    md.append(f"- 「未载明」的表：{', '.join(seal_undeclared) if seal_undeclared else '无'}")

    md.append("\n## B4 章节归属可解析\n")
    if chapter_note:
        md.append(f"- ⚠️ {chapter_note}")
    else:
        md.append(f"- 01c 章节数：{len(chapter_ids)}")
        md.append(f"- chapter_id 无法解析的表：{', '.join(unresolved) if unresolved else '无'}")

    md.append("\n## B5 一致性规则齐备（只查不算价）\n")
    md.append(f"- 已覆盖：{', '.join(rules_covered) if rules_covered else '无'}")
    md.append(f"- 缺失：{', '.join(rules_missing) if rules_missing else '无'}")

    md.append("\n## B7 表格数（与招标商务格式章比对）\n")
    md.append(f"- 03c 列出：{total} 张")
    md.append("- 招标商务格式章要求表数：⚠️ **② 不读招标原文，不可独立机检**——"
              "该条以 ① 抽取声明为准（① `BUSINESS_FORMS` 为按本项目第七章商务标部分抽取的常量，"
              "换项目须重新抽取后覆盖，见① README「已知限制」）。"
              "表格↔任务卡一一对应闭合属 D 类，由 `check_compliance.py` 唯一实现。")

    with open(os.path.join(out_dir, "business-check.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")

    # ---------------- 输出 JSON ----------------
    report = {
        "schema_version": "0.1",
        "check": "M8-business",
        "forms_total": total,
        "b1_zero_amount": {
            "verdict": "blocked" if blocked else "passed",
            "blocking": [{"form_id": a, "field": b, "type": c, "sample": d}
                         for a, b, c, d, _ in findings],
            "warnings": [{"form_id": a, "field": b, "type": c, "sample": d}
                         for a, b, c, d, _ in warnings],
        },
        "b2_required_fields_missing": rf_missing,
        "b3_seal_missing": seal_missing,
        "b3_seal_undeclared": seal_undeclared,
        "b4_chapter": {"note": chapter_note,
                       "chapter_count": len(chapter_ids) if chapter_ids is not None else None,
                       "unresolved": unresolved},
        "b5_consistency_rules": {"covered": rules_covered, "missing": rules_missing},
        "b7_form_count": {"listed": total,
                          "tender_expected": None,
                          "note": "② 不读招标原文，不可独立机检；以 ① 抽取声明为准"},
        "blocked": blocked,
    }
    with open(os.path.join(out_dir, "business-check.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"[M8] 商务表 {total} 张 ｜ B1 零金额：{verdict}")
    if findings:
        for fid, field, desc, sample, _ in findings:
            print(f"      阻断：{fid}.{field} 检出{desc}「{sample}」")
    if warnings:
        print(f"      提示：{len(warnings)} 处疑似金额，见 business-check.md")
    print(f"      B2 缺必填字段 {len(rf_missing)} ｜ B3 缺签章 {len(seal_missing)}"
          f"（未载明 {len(seal_undeclared)}）")
    print(f"      B4 章节未解析 {len(unresolved)} ｜ B5 规则缺失 {len(rules_missing)}")
    print(f"      产出：{out_dir}/business-check.md, business-check.json")

    if blocked:
        sys.exit(1)


if __name__ == "__main__":
    sys.exit(main())
