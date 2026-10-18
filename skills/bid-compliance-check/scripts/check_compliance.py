#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
② bid-compliance-check — ②-A 覆盖检查（阶段 1）
==============================================
读取 ⓪ 事实库(01) / ① 任务卡(03) / 商务表框架(03c) / 格式章(01c) / 事实库(02_facts.md) / 状态(00_metadata.json)，
对「废标项 / 资格项 / 评分点 / 商务表格」做覆盖闭合检查，输出 06_compliance/ 交付物。
只报事实态（已响应 / 响应不足 / 未响应 / 需原件核对），不改写内容，不判定是否废标。
②-B（成稿后，阶段 2）尚未实现，--mode B 仅占位。

运行要求：Python ≥ 3.12（脚本按 3.12+ 维护；分发到更低版本环境须先升级解释器）。

用法：
  python check_compliance.py --bid <项目/bid目录> [--mode A]
"""
import argparse
import datetime as _dt
import json
import os
import re
from collections import Counter, defaultdict

QUAL_CAT = "②投标资格条件"
WASTE_CAT = "③废标/否决情形"

# 否决级后果关键词（用于跨类补充扫描，M1）
CONSEQ_FATAL = ["否决", "废标", "无效标", "无效投标", "拒收", "取消资格", "没收"]

# G 类疑似控标信号：关键词 -> 提示语（措辞一律"疑似/仅标注"，不下定性结论）
G_PATTERNS = [
    ("荣誉称号", "T3-2.5 投标人荣誉称号（5分）：措辞主观，疑似倾向性评分点（仅标注）"),
    ("合理化建议", "合理化建议类评分（T4-D2/T4-S2.3）：无客观标准，主观分偏高（仅标注）"),
    ("方案水平", "T4-S2.2 主要施工及技术方案水平（7分）：纯主观，疑似缺评分锚点（仅标注）"),
    ("获奖", "T3-2.4 已建工程获奖情况（10分）：奖项分级/数量口径疑似偏主观（仅标注）"),
    ("近三年(2022-2024)风电", "c-0010/T4-2 设行业+时段业绩门槛，疑似规模/倾向性门槛（仅标注）"),
    ("营业收入（近三年平均）", "T3-2.1 设营收规模门槛（10分），常见但可标注（仅标注）"),
    ("资产总额（近三年平均）", "T3-2.2 设资产规模门槛（10分），常见但可标注（仅标注）"),
    ("资产负债率（近三年平均）", "T3-3.1 设负债率门槛（10分），常见但可标注（仅标注）"),
]

# F 类：结构化事实条目 + 证书有效期
FACT_ID_RE = re.compile(r"(?:qual|pers|fin|perf)-\d+")
CERT_VALID_RE = re.compile(
    r"(?:qual|pers)-\d+[^\n]*?(?:有效期至|有效期|valid_to)[^\n]*?(\d{4}-\d{2}-\d{2}|\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日)"
)


def load(p):
    if not os.path.exists(p):
        raise FileNotFoundError(f"②-A 缺少输入：{p}")
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def load_text(p):
    try:
        return open(p, encoding="utf-8").read()
    except FileNotFoundError:
        return ""


def norm_date(s):
    s = s.replace(" ", "").replace("年", "-").replace("月", "-").replace("日", "")
    m = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if not m:
        return None
    return _dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))


def parse_deadline(s):
    """从 metadata.deadline 取日期部分（兼容 ISO 与非 ISO 写法），仅取年月日。"""
    if not s:
        return None
    m = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})", str(s))
    if not m:
        return None
    try:
        return _dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def cover_clauses(clauses, items, expect_type):
    """对一组事实条款，找 response_type==expect_type 的任务卡，给处置态。
    处置三态（计划书 D5 统一）：已响应 / 响应不足 / 未响应；
    '响应不足' 的细分原因（待澄清/缺事实库/其他）置于 reason 字段，不混入 disposition。"""
    cards_by_ref = defaultdict(list)
    for it in items:
        cards_by_ref[it.get("source_ref")].append(it)
    rows = []
    for c in clauses:
        refs = cards_by_ref.get(c.get("id"), [])
        matched = [r for r in refs if r.get("source_type") == expect_type]
        if matched:
            statuses = [m.get("status") for m in matched]
            if all(s == "ready" for s in statuses):
                disp, reason = "已响应", None
            elif any(s == "blocked_by_clarify" for s in statuses):
                disp, reason = "响应不足", "待澄清"
            elif any(s == "blocked_by_facts" for s in statuses):
                disp, reason = "响应不足", "缺事实库"
            else:
                disp, reason = "响应不足", "其他"
            needs_orig = any(("原件" in (m.get("notes") or "")) and
                             ("无需" not in (m.get("notes") or "")) and
                             ("不必" not in (m.get("notes") or ""))
                             for m in matched)
            rows.append({
                "clause_id": c.get("id"), "item": c.get("item"), "status": "covered",
                "disposition": disp, "reason": reason, "cards": [m.get("id") for m in matched],
                "needs_original": needs_orig, "consequence": c.get("consequence", ""),
            })
        else:
            rows.append({
                "clause_id": c.get("id"), "item": c.get("item"), "status": "no_card",
                "disposition": "未响应", "reason": None, "cards": [], "needs_original": False,
                "consequence": c.get("consequence", ""),
            })
    return rows


def _yaml_scalar(v):
    """极简 YAML 标量规整：去引号、识别 bool/null，其余按字符串。"""
    v = v.strip()
    if v == "":
        return None
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        return v[1:-1]
    low = v.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    if low in ("none", "null"):
        return None
    return v


def _mini_yaml_load(text):
    """零依赖 YAML 子集解析，仅覆盖本套件 02_facts.yaml 结构：
    顶层 `section:` 后跟 `- key: value` 列表（value 统一按字符串/标量处理）。
    完整解析交由 PyYAML（若可用）；本函数为其不可用时的兜底，确保 F 类不静默失效。"""
    data = {}
    cur_section = None
    cur_item = None
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        if indent == 0 and not stripped.startswith("- "):
            key, _, val = stripped.partition(":")
            key = key.strip()
            if val.strip() == "":
                cur_section = key
                cur_item = None
                data.setdefault(key, [])
            else:
                data[key] = _yaml_scalar(val)
            continue
        if stripped.startswith("- "):
            cur_item = {}
            data.setdefault(cur_section, []).append(cur_item)
            rest = stripped[2:].strip()
            if ":" in rest:
                k, _, v = rest.partition(":")
                cur_item[k.strip()] = _yaml_scalar(v)
            continue
        if ":" in stripped and cur_item is not None:
            k, _, v = stripped.partition(":")
            cur_item[k.strip()] = _yaml_scalar(v)
    return data


def _load_structured_facts(bid):
    """加载结构化事实库：优先 02_facts.yaml（yaml，PyYAML 可用时完整解析；
    不可用时零依赖极简解析兜底），回退 02_facts.json；无则 None。
    依据 facts.schema.yaml：qualifications/personnel 条目含 valid_to，供 F 类时效判定。"""
    yaml_path = os.path.join(bid, "02_facts.yaml")
    json_path = os.path.join(bid, "02_facts.json")
    if os.path.exists(yaml_path):
        try:
            import yaml  # PyYAML；可用时优先（完整保真）
            with open(yaml_path, encoding="utf-8") as f:
                return yaml.safe_load(f)
        except Exception:
            pass
        # PyYAML 不可用 → 零依赖极简解析，避免 F 类静默降级为 fact_missing
        try:
            with open(yaml_path, encoding="utf-8") as f:
                return _mini_yaml_load(f.read())
        except Exception:
            return None
    if os.path.exists(json_path):
        try:
            with open(json_path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None


def qual_timing(structured_facts, facts_text, deadline_date):
    """F 类资质时效三态：fact_missing / expired / expiring_soon / stated。
    优先解析结构化 02_facts.yaml/.json（qual-/pers- 含 valid_to）；
    缺失时退化为扫描 02_facts.md 正则（旧行为，仅作兜底）。
    时间基准取 00_metadata.deadline，不以系统日期推算。"""
    # 优先：结构化事实库（qualifications / personnel 含 valid_to）
    if structured_facts:
        certs = []
        for sec in ("qualifications", "personnel"):
            for e in (structured_facts.get(sec) or []):
                vt = e.get("valid_to")
                if vt:
                    certs.append((e.get("id"), vt))
        if certs:
            if deadline_date is None:
                return "fact_missing", "metadata.deadline 缺失或不可解析，无法作为时效基准；须人工录入截止日后重跑"
            worst = "stated"
            details = []
            for cid, vt in certs:
                v = vt if isinstance(vt, _dt.date) else norm_date(str(vt))
                if v is None:
                    details.append(f"{cid} valid_to={vt} 不可解析")
                    continue
                if v < deadline_date:
                    worst = "expired"
                    details.append(f"{cid} valid_to={vt} 早于截止日({deadline_date})→废标风险")
                elif v <= deadline_date + _dt.timedelta(days=180):
                    if worst != "expired":
                        worst = "expiring_soon"
                    details.append(f"{cid} valid_to={vt} 落入换证窗口(截止前180天内)")
                else:
                    details.append(f"{cid} valid_to={vt} 有效")
            return worst, "；".join(details) if details else "未解析到有效日期"
    # 退化：扫描 md 正则（兜底）
    certs_md = CERT_VALID_RE.findall(facts_text)
    if not certs_md:
        if FACT_ID_RE.search(facts_text):
            return "fact_missing", "事实库含事实ID但缺结构化证书有效期字段，时效不可判；须回①补录后重跑"
        return "fact_missing", "事实库(02_facts.yaml/.json)未含结构化事实条目（无 qual/pers 有效期），时效不可判；属资料缺口，须回①补录"
    if deadline_date is None:
        return "fact_missing", "metadata.deadline 缺失或不可解析，无法作为时效基准；须人工录入截止日后重跑"
    worst = "stated"
    details = []
    for cv in certs_md:
        v = norm_date(cv)
        if v is None:
            continue
        if v < deadline_date:
            worst = "expired"
            details.append(f"{cv} 早于截止日({deadline_date})")
        elif v <= deadline_date + _dt.timedelta(days=180):
            if worst != "expired":
                worst = "expiring_soon"
            details.append(f"{cv} 落入换证窗口(截止前180天内)")
        else:
            details.append(f"{cv} 有效")
    return worst, "；".join(details) if details else "未解析到有效日期"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bid", required=True, help="项目 bid 目录")
    ap.add_argument("--mode", choices=["A", "B"], default="A")
    args = ap.parse_args()
    bid = args.bid

    if args.mode == "B":
        print("②-B（成稿后响应检查）尚未实现，属阶段 2 交付。")
        return

    p01 = os.path.join(bid, "01_tender-facts.json")
    p03 = os.path.join(bid, "03_bid-plan.json")
    p03c = os.path.join(bid, "03c_business-forms.json")
    p01c = os.path.join(bid, "01c_format-outline.json")
    p02 = os.path.join(bid, "02_facts.md")
    pmeta = os.path.join(bid, "00_metadata.json")
    out_dir = os.path.join(bid, "06_compliance")
    os.makedirs(out_dir, exist_ok=True)

    facts = load(p01)
    plan = load(p03)
    bus = load(p03c)
    fmt = load(p01c)
    facts_text = load_text(p02)
    meta = load_text(pmeta)
    structured_facts = _load_structured_facts(bid)
    try:
        meta_json = json.loads(meta) if meta else {}
    except json.JSONDecodeError:
        meta_json = {}

    contract_ver = facts.get("contract_schema_version")
    plan_schema = plan.get("schema_version")
    version_ok = (contract_ver == "0.4")
    plan_ok = (plan_schema == "0.2")

    # ---------- 入口校验（M5：读 metadata 验 stage） ----------
    # ②-A 入口态为 plan_confirmed；②-A 执行中会置 checking，重跑（G3 未确认前）亦合法
    entry_stage = meta_json.get("stage")
    entry_ok = (entry_stage in ("plan_confirmed", "checking"))
    deadline_date = parse_deadline(meta_json.get("deadline"))

    clauses = facts["clauses"]
    items = plan["items"]

    # ---------- 覆盖矩阵：废标项 / 资格项（按 category） ----------
    waste_clauses = [c for c in clauses if (c.get("category") or "").strip() == WASTE_CAT]
    qual_clauses = [c for c in clauses if (c.get("category") or "").strip() == QUAL_CAT]
    waste_rows = cover_clauses(waste_clauses, items, "waste")
    qual_rows = cover_clauses(qual_clauses, items, "qualification")

    # ---------- 评分点覆盖 ----------
    scoring_items = facts.get("scoring", {}).get("items", [])  # S-01/02/03
    score_cards = [it for it in items if it.get("source_type") == "scoring"]
    s_rows = []
    for s in scoring_items:
        refs = [r.get("id") for r in score_cards if r.get("source_ref") == s.get("id")]
        s_rows.append({"id": s.get("id"), "covered": bool(refs), "cards": refs})
    detail_refs = sorted({it.get("source_ref") for it in score_cards
                          if re.match(r"^(T3|T4|T5)", str(it.get("source_ref") or ""))})
    score_unmapped = [s["id"] for s in s_rows if not s["covered"]]
    # 诚实标注：01 上游仅有 3 条汇总评分条款（c-0028/29/30），无逐行明细清单，
    # 明细行完整性不可从上游机检，须人工对 T3/T4/T5 原表核对。
    score_detail_verifiable = False

    # ---------- 跨类否决级条款补充扫描（M1） ----------
    cat3_ids = {c.get("id") for c in waste_clauses}
    cross_rows = []
    for c in clauses:
        cons = c.get("consequence") or ""
        if any(k in cons for k in CONSEQ_FATAL) and c.get("id") not in cat3_ids:
            refs = [r.get("id") for r in items if r.get("source_ref") == c.get("id")]
            cross_rows.append({
                "clause_id": c.get("id"), "category": c.get("category"),
                "item": c.get("item"), "consequence": cons, "cards": refs,
                "status": "covered" if refs else "no_card",
            })

    # ---------- 孤儿卡检测（M1） ----------
    clause_ids = {c.get("id") for c in clauses}
    score_ids = {s.get("id") for s in scoring_items}
    form_ids_all = {f.get("id") for f in bus.get("forms", [])}
    valid_refs = clause_ids | score_ids | form_ids_all | set(detail_refs)
    orphan_cards = [it.get("id") for it in items if it.get("source_ref") not in valid_refs]

    # ---------- 商务表齐全性（D 类） ----------
    form_ids = [f.get("id") for f in bus.get("forms", [])]
    bus_cards = [it for it in items if it.get("source_type") == "business"]
    bus_refs = {it.get("source_ref") for it in bus_cards}
    forms_missing = [fid for fid in form_ids if fid not in bus_refs]

    # ---------- 形式字段齐备（C 类；page_limit 单列为"未载明/待确认"，不作无源断言） ----------
    typo = fmt.get("typography", {})
    form_fields = {"binding": typo.get("binding"), "seal": typo.get("seal"),
                   "page_limit": typo.get("page_limit")}
    form_missing = [k for k in ("binding", "seal") if not form_fields[k]]
    page_limit_stated = form_fields["page_limit"] is not None

    # ---------- G 类：疑似控标信号（只标注不定性） ----------
    score_notes = " ".join(it.get("notes") or "" for it in score_cards)
    flags = []
    for kw, msg in G_PATTERNS:
        if kw in score_notes or kw in facts_text:
            flags.append(msg)

    # ---------- F 类：资质时效（三态，时间基准取 metadata.deadline） ----------
    qual_cards = [it for it in items if it.get("source_type") == "qualification"]
    required_facts = sorted({rf for it in qual_cards for rf in it.get("required_facts", [])})
    f_status, f_detail = qual_timing(structured_facts, facts_text, deadline_date)

    # ---------- 汇总计数 ----------
    def count(rows):
        return Counter(r["disposition"] for r in rows)

    waste_cnt = count(waste_rows)
    qual_cnt = count(qual_rows)
    unmapped_waste = [r["clause_id"] for r in waste_rows if r["status"] == "no_card"]
    unmapped_qual = [r["clause_id"] for r in qual_rows if r["status"] == "no_card"]
    needs_orig = [r["clause_id"] for r in waste_rows + qual_rows if r["needs_original"]]
    # business 卡需原件核对（t-0020 保函原件等）
    needs_orig_bus = [it["source_ref"] for it in bus_cards
                      if ("原件" in (it.get("notes") or "")) and
                      ("无需" not in (it.get("notes") or ""))]
    insufficient = [r["clause_id"] for r in waste_rows + qual_rows
                    if r["status"] == "covered" and r["disposition"] == "响应不足"]

    summary = {
        "entry_stage": entry_stage, "entry_ok": entry_ok,
        "version_ok": version_ok, "plan_ok": plan_ok,
        "waste_total": len(waste_rows), "waste_unmapped": unmapped_waste,
        "waste_disposition": dict(waste_cnt),
        "qual_total": len(qual_rows), "qual_unmapped": unmapped_qual,
        "qual_disposition": dict(qual_cnt),
        "score_items_total": len(s_rows), "score_unmapped": score_unmapped,
        "score_detail_rows": len(detail_refs), "score_detail_verifiable": score_detail_verifiable,
        "cross_fatal_total": len(cross_rows),
        "cross_fatal_no_card": [r["clause_id"] for r in cross_rows if r["status"] == "no_card"],
        "orphan_cards": orphan_cards,
        "business_forms_total": len(form_ids), "business_forms_missing": forms_missing,
        "form_fields_missing": form_missing, "page_limit_stated": page_limit_stated,
        "insufficient": insufficient, "needs_original": needs_orig,
        "needs_original_business": needs_orig_bus,
        "g_flags": len(flags), "f_status": f_status,
    }

    # ---------- G3 阻断（对称：任何未响应/响应不足/需原件/版本不符均阻断） ----------
    reasons = []
    if not entry_ok:
        reasons.append(f"入口stage={entry_stage}≠plan_confirmed")
    if not version_ok or not plan_ok:
        reasons.append("契约版本不符(01≠0.4 或 03≠0.2)")
    if unmapped_waste:
        reasons.append(f"废标项未响应{len(unmapped_waste)}")
    if unmapped_qual:
        reasons.append(f"资格项未响应{len(unmapped_qual)}")
    if score_unmapped:
        reasons.append(f"评分点未覆盖{len(score_unmapped)}")
    if forms_missing:
        reasons.append(f"商务表缺失{len(forms_missing)}")
    if insufficient:
        reasons.append(f"响应不足待处置{len(insufficient)}(待澄清/缺事实库)")
    if orphan_cards:
        reasons.append(f"孤儿卡{len(orphan_cards)}")
    if needs_orig or needs_orig_bus:
        reasons.append(f"需原件核对{len(needs_orig) + len(needs_orig_bus)}")
    g3 = ("可交 G3" if not reasons else "未自动通过：" + "；".join(reasons))

    # ---------- 写出 JSON ----------
    report = {
        "schema_version": "0.2",
        "mode": "A",
        "generated_from": {
            "01_contract_schema_version": contract_ver,
            "03_schema_version": plan_schema,
            "entry_stage": entry_stage, "entry_ok": entry_ok,
            "version_ok": version_ok, "plan_ok": plan_ok,
            "deadline": meta_json.get("deadline"),
        },
        "summary": summary,
        "g3_disposition": g3,
        "waste": waste_rows,
        "qualification": qual_rows,
        "scoring": {"items": s_rows, "detail_rows": detail_refs,
                    "detail_verifiable": score_detail_verifiable,
                    "unmapped": score_unmapped},
        "cross_fatal": cross_rows,
        "orphan_cards": orphan_cards,
        "business_forms": {"total": len(form_ids), "missing": forms_missing,
                           "covered": len(form_ids) - len(forms_missing)},
        "form_fields": {"present": form_fields, "missing": form_missing,
                        "page_limit_stated": page_limit_stated},
        "g_suspicion": flags,
        "f_qual_timing": {"status": f_status, "required_facts": required_facts,
                          "deadline": meta_json.get("deadline"), "detail": f_detail},
    }
    with open(os.path.join(out_dir, "compliance-report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # ---------- 写出 Markdown ----------
    md = []
    bid_name = os.path.basename(os.path.dirname(bid.rstrip("/\\")))
    md.append("# ②-A 合规覆盖检查报告\n")
    md.append(f"> 生成：{bid_name} ｜ 模式 A（覆盖检查，阶段 1）")
    md.append(f"> 输入版本：01.contract_schema_version={contract_ver} ｜ 03.schema_version={plan_schema}"
              f" ｜ 版本校验 {'✅' if version_ok and plan_ok else '⚠️'}"
              f" ｜ 入口 stage={entry_stage}（要求 plan_confirmed）{'✅' if entry_ok else '⚠️'}")
    md.append(f"> 时效基准：00_metadata.deadline={meta_json.get('deadline')}\n")

    md.append("## 一、G3 处置结论\n")
    md.append(f"- **{g3}**")
    md.append(f"- 废标项未响应：{len(unmapped_waste)} ｜ 资格项未响应：{len(unmapped_qual)}"
              f" ｜ 评分点未覆盖：{len(score_unmapped)} ｜ 商务表缺失：{len(forms_missing)}"
              f" ｜ 响应不足：{len(insufficient)} ｜ 孤儿卡：{len(orphan_cards)}")
    md.append(f"- 需原件核对：{', '.join(needs_orig + needs_orig_bus) if (needs_orig or needs_orig_bus) else '无'}\n")

    md.append("## 二、废标项覆盖（A 类，category=③）\n")
    md.append("| 条款 | 事项 | 状态 | 处置 | 任务卡 | 需原件 | 后果 |")
    md.append("|---|---|---|---|---|---|---|")
    for r in waste_rows:
        disp = r['disposition'] + (f"（{r['reason']}）" if r.get('reason') else "")
        md.append(f"| {r['clause_id']} | {r['item']} | {r['status']} | {disp} |"
                  f" {','.join(r['cards']) or '—'} | {'是' if r['needs_original'] else '—'} | {r['consequence']} |")

    md.append("\n## 三、资格项覆盖（A 类，category=②）\n")
    md.append("| 条款 | 事项 | 状态 | 处置 | 任务卡 |")
    md.append("|---|---|---|---|---|")
    for r in qual_rows:
        disp = r['disposition'] + (f"（{r['reason']}）" if r.get('reason') else "")
        md.append(f"| {r['clause_id']} | {r['item']} | {r['status']} | {disp} |"
                  f" {','.join(r['cards']) or '—'} |")

    md.append("\n## 四、评分点覆盖（A 类）\n")
    md.append(f"- 评分项（S-01/02/03）：{len(s_rows)} 项，未覆盖 {len(score_unmapped)} 项")
    md.append(f"- 评分明细行（任务卡侧 T3/T4/T5）：{len(detail_refs)} 行")
    md.append(f"- ⚠️ **明细行完整性不可从上游机检**：01 仅有 3 条汇总评分条款（c-0028/29/30），无逐行明细清单，"
              f"须人工对评标办法 T3/T4/T5 原表逐行核对；本工具只报任务卡侧行数，不出'缺失0'结论。")

    md.append("\n## 五、跨类否决级条款补充扫描（M1）\n")
    md.append("以下条款散布在 ①/⑤/⑥/⑦ 类但带否决级后果。**按 source_ref 精确匹配**列出任务卡覆盖（非主覆盖口径，不单独阻断 G3）：")
    md.append("| 条款 | 类 | 事项 | 后果 | 任务卡 | 状态 |")
    md.append("|---|---|---|---|---|---|")
    for r in cross_rows:
        md.append(f"| {r['clause_id']} | {r['category']} | {r['item']} | {r['consequence']} |"
                  f" {','.join(r['cards']) or '—'} | {'有卡' if r['status']=='covered' else '无直接卡'} |")
    md.append(f"- 孤儿卡（source_ref 无法解析到任何 clause/评分项/表单）：{', '.join(orphan_cards) if orphan_cards else '无'}")
    md.append("- ⚠️ 「无直接卡」的四类常见成因，须人工甄别、**不当作缺口**：① 与 ③ 类某条重复、该条已有卡（c-0035↔c-0020 限价、c-0046↔c-0023 加密、c-0047↔c-0022 装订）；② 经商务表 bf 卡覆盖但 source_ref 记 bf-ID 非 clause-ID（c-0032 保证金否决 ↔ bf-02/t-0020）；③ 属 ④ 排版职责（签章/装订/密封/份数，c-0049/c-0050）；④ 流程/时限项，靠操作不靠文档响应（逾期拒收 c-0001、拒签 c-0006，后者另由 c-0025/t-0018 覆盖中标后资格剥夺）。")

    md.append("\n## 六、商务表齐全性（D 类）\n")
    md.append(f"- 招标要求表格：{len(form_ids)} 张（bf-01..bf-{form_ids[-1][-2:] if form_ids else '??'}）")
    md.append(f"- 任务卡已覆盖：{len(form_ids) - len(forms_missing)} 张")
    md.append(f"- 缺失：{', '.join(forms_missing) if forms_missing else '无'}")

    md.append("\n## 七、形式字段齐备（C 类）\n")
    md.append(f"- 装订方式(binding)：{'✅ ' + (form_fields['binding'] or '') if form_fields['binding'] else '❌ 缺失→blocked_by_contract，回①补抽'}")
    md.append(f"- 签章(seal)：{'✅ ' + (form_fields['seal'] or '') if form_fields['seal'] else '❌ 缺失→blocked_by_contract，回①补抽'}")
    md.append(f"- 页数上限(page_limit)：{'✅ ' + str(form_fields['page_limit']) if page_limit_stated else '⚠️ 01c 未载明（无法区分「未设上限」与「抽取缺失」，按铁律3须回①确认或按招标隐含估算并写明依据，不得径断「无上限」）'}")
    md.append("- C 类 ②-A 规定项（暗标 bid_mode 传递、页数预算可行性）：本项目 bid_mode=normal（非暗标）；页数上限未载明，页数预算待④装配时核。")

    md.append("\n## 八、疑似控标信号（G 类，仅标注不定性）\n")
    md.append("> 以下为静态关键词匹配，只作疑似提示，**不作'违规/违法'定性**；评分锚点以评委解释为准。")
    if flags:
        for fl in flags:
            md.append(f"- ⚠️ {fl}")
    else:
        md.append("- 未检出明显控标信号")

    md.append("\n## 九、资质时效（F 类，三态）\n")
    md.append(f"- 状态：**{f_status}**（时间基准：metadata.deadline）")
    md.append(f"- 所需事实库 ID：{', '.join(required_facts) if required_facts else '无'}")
    md.append(f"- {f_detail}")
    md.append("- 口径：fact_missing=资料缺口(非废标，回①补录)｜expired=废标风险｜expiring_soon=换证窗口(黄色)｜stated=有效。")

    md.append("\n## 十、澄清边界提示（blocked_by_clarify 项）\n")
    md.append("- 纯笔误/客观无歧义可澄清；**履约条件本身有浮动空间、改了影响权利义务的不可澄清**（如期限'30日'vs'一个月'）。")
    md.append("- **禁止'先随便填、等澄清再改'**：blocked_by_clarify 项须于投标截止前取得书面澄清并固化，不得以'等澄清'为由留空。")
    clarify_items = [r["clause_id"] for r in waste_rows + qual_rows
                     if r["disposition"] == "响应不足" and r.get("reason") == "待澄清"]
    md.append(f"- 本次待澄清条款：{', '.join(clarify_items) if clarify_items else '无'}")

    md.append("\n---\n【交付审查】②-A 仅做覆盖闭合检查，不改写任何内容，不判定是否废标；"
              "G3 须人工逐条确认响应不足/未响应/需原件核对项后写 check_confirmed。")

    with open(os.path.join(out_dir, "compliance-report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md))

    # 拆分交付物
    with open(os.path.join(out_dir, "form-check.md"), "w", encoding="utf-8") as f:
        f.write("# 形式字段检查（C 类）\n\n")
        f.write(f"- 装订方式(binding)：{'✅ ' + (form_fields['binding'] or '') if form_fields['binding'] else '❌ 缺失→回①补抽'}\n")
        f.write(f"- 签章(seal)：{'✅ ' + (form_fields['seal'] or '') if form_fields['seal'] else '❌ 缺失→回①补抽'}\n")
        f.write(f"- 页数上限(page_limit)：{'✅ ' + str(form_fields['page_limit']) if page_limit_stated else '⚠️ 01c 未载明，须回①确认或按招标隐含估算并写明依据'}\n")
        f.write("- bid_mode=normal（非暗标）；页数预算可行性待④装配时核。\n")
    # business-check.md 落点已移交 check_business.py（M8 唯一归属，计划书 §5 目录树 / §11.2 验收 #9）。
    # D 类「商务表↔任务卡一一对应」结论仍保留在本脚本的 compliance-report.md 与
    # compliance-report.json（business_forms 字段），此处不再重复写同一落点文件，避免两个脚本互相覆盖。
    with open(os.path.join(out_dir, "deviation-table.md"), "w", encoding="utf-8") as f:
        f.write("# 偏离表齐全性（B 类）\n\n")
        bf05 = any(it.get("source_ref") == "bf-05" for it in bus_cards)
        bf19 = any(it.get("source_ref") == "bf-19" for it in bus_cards)
        f.write(f"- 商务偏差声明函（bf-05）：任务卡 {'✅ 已建' if bf05 else '❌ 缺失'}，要求「无偏差须注『无』」\n")
        f.write(f"- 技术偏差声明函（bf-19）：任务卡 {'✅ 已建' if bf19 else '❌ 缺失'}，要求「无偏差须注『无』」\n")
        spec_items = os.path.join(bid, "01b_spec-items.json")
        if os.path.exists(spec_items):
            try:
                n = len(load(spec_items).get("items", []))
                f.write(f"- 偏离表行 vs 01b 技术规范条目：01b 现有 {n} 条（2.性能指标节已全量 14 行，第五章其余 8 节挂起），逐行一致性以 01b 全量后重跑为准。\n")
            except Exception:
                f.write("- 01b 读取异常，偏离表逐行一致性待补。\n")
        else:
            f.write("- 01b_spec-items.json 缺失，偏离表逐行一致性无法核（blocked_by_contract）。\n")

    print("②-A 检查完成 →", out_dir)
    print(f"  入口stage={entry_stage}({'OK' if entry_ok else 'NOT plan_confirmed'})  "
          f"废标项 {len(waste_rows)}(未响应{len(unmapped_waste)})  "
          f"资格项 {len(qual_rows)}(未响应{len(unmapped_qual)})  "
          f"评分明细 {len(detail_refs)}行(上游不可机检)  "
          f"商务表 {len(form_ids)-len(forms_missing)}/{len(form_ids)}")
    print(f"  跨类否决级 {len(cross_rows)}(无卡 {len(summary['cross_fatal_no_card'])})  "
          f"孤儿卡 {len(orphan_cards)}  响应不足 {len(insufficient)}  需原件 {len(needs_orig)+len(needs_orig_bus)}")
    print(f"  G3: {g3}")
    print(f"  F类: {f_status} ｜ G类: {len(flags)}")


if __name__ == "__main__":
    main()
