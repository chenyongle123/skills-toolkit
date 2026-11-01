# -*- coding: utf-8 -*-
"""
build_task_cards.py —— ① bid-response-plan 任务卡与目录骨架生成（03 / 04）
计划书 §4.1（M1 任务卡）/ 计划书 §4.2（M3 目录骨架）/ 计划书 §6.2（契约）。

职责边界：任务卡只回答"谁在哪个章节、用什么形式、达到什么篇幅、响应哪
一条、状态如何"——**不写正文、不判定合规**（正文属 ③，合规判定属 ②）。

v0.24.0 派生式重构（修复缺陷：任务卡硬编码）：旧版 TASKS/SCORING_DETAIL
为示例项目的逐字硬编码（48+31 张卡不随 01 内容变化，金额/权重/年份/分值
等招标值内嵌代码）。现改为全部从 01_tender-facts.json 派生：
- 条款卡：01.clauses 逐条生成（category→source_type；item/text/consequence
  如实流入 notes——招标值经条款原文透传，本代码零项目级内嵌值）；
- 评分卡：01.scoring.items 逐条生成（事项/分值来自 01；coverage 按评分卡
  source_ref 与 01 真实对账，每个评分项一张卡 → unmapped 恒空才可交 G1）；
- 商务表卡：03c BUSINESS_FORMS 逐表镜像（表单类型学常量 FORM_HINT 随 03c
  一并换项目复核，不含任何招标值）。
章节挂接（v0.26.0 锚定上下文 rewiring）：条款/评分/商务三卡 chapter_id
一律经 set_chapter_context 后的锚定上下文解析（链内=当前 01c 派生树，
独立用法=FORMAT_CHAPTERS 常量兜底树）——逐字命中优先，未命中走语义
槽（商务/技术/价格/报价），槽空 fail-loud 报错给人工定锚，不静默挂错章。

03_bid-plan.json 关键口径：
- preconditions[].p-0001 补遗/澄清对照（三态 pass/fail/unknown，未对照即阻断 G1）；
- coverage.mapped/unmapped 按评分卡 source_ref 与 01.scoring.items 真实对账；
- 04_outline.json 字段集为计划书 §6.2 D4 修正版（order/parent/depends_on/
  word_target/scoring_refs/status/notes），章名逐字取自 01c（铁律 2）。

独立用法：python build_task_cards.py --bid <项目>/bid
"""
import argparse, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from parse_format_outline import (build_01c, chapter_context_titles,
                                  resolve_chapter_id)
from parse_business_forms import (BUSINESS_FORMS, resolve_form_chapter,
                                  validate_forms_chapter_linkage)

# ---------- 01.clauses.category → 03.source_type ----------
CATEGORY_TO_TYPE = {
    "②投标资格条件": "qualification",
    "③废标/否决情形": "waste",
}
# 其余类别（①时间节点与流程/④评标与定标标准/⑤履约保证金与商务条款/
# ⑥合同关键约束/⑦形式与程序要求/未知类别等）→ business（须有卡，兼满足
# ② cross_fatal：非③类条款含致命后果亦须有落点）。

# ---------- 条款章节启发式（item+text 关键词 → 01c 章节标题，顺序匹配） ----------
FALLBACK_CHAPTER = "招标文件要求提供的其他材料"
CHAPTER_RULES = [
    (("保证金", "保函"), "投标保证金格式"),
    (("审计", "财务", "资信", "信用"), "财务及资信状况"),
    (("业绩",), "已完工的业绩表"),
    (("建造师", "项目经理", "负责人"), "项目实施方案（由投标人自行编制）"),
    (("报价", "限价", "价格", "总价", "下浮", "费用"), "报价汇总表"),
    (("偏差",), "商务偏差声明函"),
    (("截止", "有效期", "工期"), "投标函格式"),
    (("分包",), "施工分包情况表（适用于投标人不具备招标文件所要求的施工资质的情况）"),
    (("声明", "承诺", "评审", "资格", "后审", "人员", "机构", "诉讼", "仲裁"),
     "资格审查文件"),
]

# ---------- 条款响应形式启发式（默认 scan：证照/截图/证明/现场核查类） ----------
RESPONSE_RULES = [
    (("偏差", "声明", "承诺"), "letter"),
    (("报价", "限价", "总价", "下浮", "费用", "清单"), "table"),
]

# ---------- required_facts 信号（条款 text/item 与评分 item 共用） ----------
FACT_RULES = [
    (("审计报告", "财务状况", "资产负债"), ["fin-2022", "fin-2023", "fin-2024"]),
    (("银行资信", "资信证明"), ["fin-2022"]),
    (("资质", "注册资本"), ["qual-001"]),
    (("业绩",), ["perf-001"]),
    (("建造师", "项目经理", "负责人", "人员", "机构配置"), ["pers-001"]),
    (("主要设备", "制造商", "装备配置"), ["eq-001"]),
]

# ---------- 评分卡章节/形式启发式（item 关键词，默认商务标/text） ----------
SCORE_CHAPTER_RULES = [
    (("报价", "价格", "费用"), "价格标"),
    (("技术", "方案", "施工组织"), "技术标"),
    (("业绩",), "已完工的业绩表"),
]
SCORE_FORM_RULES = [
    (("报价", "价格", "费用"), "table"),
    (("商务", "资信", "响应性"), "business_form"),
]

# ---------- 商务表卡类型学常量（bf-id → (response_form, word_target)） ----------
# 性质：与 03c BUSINESS_FORMS / 01c FORMAT_CHAPTERS 同源的①级设计常量，
# 只描述「每张表格以什么形式响应、篇幅档位」的类型学，**不含任何招标值**
# （金额/年份/分值等均不在内）；换项目时与 BUSINESS_FORMS 一并按格式章复核。
FORM_HINT = {
    "bf-01": ("letter", 1500), "bf-02": ("scan", 800), "bf-03": ("scan", 500),
    "bf-04": ("scan", 500), "bf-05": ("table", 1000), "bf-06": ("table", 800),
    "bf-07": ("scan", 2500), "bf-08": ("letter", 800), "bf-09": ("scan", 600),
    "bf-10": ("scan", 3000), "bf-11": ("scan", 1500), "bf-12": ("table", 600),
    "bf-13": ("table", 600), "bf-14": ("table", 600), "bf-15": ("table", 400),
    "bf-16": ("table", 400), "bf-17": ("table", 400), "bf-18": ("table", 400),
    "bf-19": ("table", 1000), "bf-20": ("table", 2000), "bf-21": ("table", 800),
    "bf-22": ("table", 1000), "bf-23": ("table", 1000), "bf-24": ("table", 800),
}

# 条款卡篇幅档位（按响应形式；类型学，非招标值）
CLAUSE_WORD_TARGET = {"letter": 800, "table": 500, "scan": 1200}

# value_state 缺值态 → blocked_by_clarify（须书面澄清后方可编制）
CLARIFY_STATES = ("external_missing", "missing", "draft", "draft_blank")


def _hit(rules_keys, text):
    """规则关键词命中判定：任一关键词为 text 子串即命中。"""
    return any(k in text for k in rules_keys)


def _match(rules, text, default):
    """顺序匹配规则表 [(关键词组, 值), ...]，未命中回退 default。"""
    for (keys, val) in rules:
        if _hit(keys, text):
            return val
    return default


def _derive_required_facts(text):
    """按条款/评分文本语义推导所需事实 id（并集、去序保真）。"""
    facts = []
    for (keys, ids) in FACT_RULES:
        if _hit(keys, text) and not any(f in facts for f in ids):
            facts.extend(ids)
    return facts


def _clause_chapter(item, text):
    """条款卡章节标题：item+text 启发式 → 交 _anchor_or_raise 锚定。

    常量树逐字命中；派生树按标题关键词走组头语义槽（含「报价」等关键词
    的条款不得被兜底章名顶掉路由）；槽空由 _anchor_or_raise fail-loud。
    """
    blob = "%s %s" % (item, text)
    return _match(CHAPTER_RULES, blob, FALLBACK_CHAPTER)


def _anchor_or_raise(title, ctx_desc):
    """章名 → 当前树 chapter_id（resolve_chapter_id）；槽空即抛错（fail-loud，
    平铺树的锚定须人工方案，不得静默挂错章）。"""
    cid = resolve_chapter_id(title)
    if cid is None:
        raise ValueError(
            "任务卡章节锚定失败：%s → 目标章名「%s」未逐字命中且无语义槽可配"
            "（当前章节树无 商务/技术/价格/报价 组头）。当前树全部章名（截断）：%s。"
            "平铺结构的格式章须人工定锚定方案后重跑" % (ctx_desc, title, chapter_context_titles()[:400]))
    return cid


def _clause_response(item, text):
    """条款卡响应形式：声明/偏差/报价类之外默认 scan（证照类）。"""
    return _match(RESPONSE_RULES, "%s %s" % (item, text), "scan")


def derive_clause_card(clause):
    """01.clauses 单条 → 条款任务卡 dict（id 由调用方统一编发）。

    招标值（金额/年份/权重/分值等）经 item/text/consequence 如实透传进
    notes——本函数不内嵌任何示例项目值。缺字段一律 .get() 兜底。
    """
    cid = clause.get("id") or ""
    item = str(clause.get("item") or "")
    text = str(clause.get("text") or "")
    conseq = str(clause.get("consequence") or "")
    category = str(clause.get("category") or "")
    stype = CATEGORY_TO_TYPE.get(category, "business")
    blob = "%s %s" % (item, text)
    facts = _derive_required_facts(blob)
    if facts:
        status = "blocked_by_facts"
    elif str(clause.get("value_state") or "") in CLARIFY_STATES:
        status = "blocked_by_clarify"
    else:
        status = "ready"
    form = _clause_response(item, text)
    parts = []
    if item:
        parts.append("【%s】" % item)
    parts.append(text or "（条款原文未载明，须核对招标文件）")
    if conseq:
        parts.append("（后果：%s）" % conseq)
    return {
        "source_type": stype, "source_ref": cid,
        "chapter_id": _anchor_or_raise(_clause_chapter(item, text), "条款卡 %s" % (cid or "?")),
        "response_form": form, "word_target": CLAUSE_WORD_TARGET.get(form, 1200),
        "required_facts": facts, "owner": "", "status": status,
        "notes": "".join(parts),
    }


def derive_scoring_card(s_item):
    """01.scoring.items 单条 → 评分任务卡 dict。

    事项与分值均来自 01（.get() 兜底）；评分响应必须以事实库为据 →
    status 恒 blocked_by_facts（与 ① gate「02_facts 可缺但告警」口径一致）。
    """
    sid = s_item.get("id") or ""
    item = str(s_item.get("item") or "")
    pts_raw = s_item.get("points")
    try:
        pts = float(pts_raw)
    except (TypeError, ValueError):
        pts = 10.0
    blob = item
    facts = _derive_required_facts(blob)
    # 「商务标/技术标/价格标」在常量树逐字命中、在派生树走组头语义槽
    # （resolve_chapter_id 关键词推导）——不做已知性降级，防技术/价格卡
    # 被兜底章名顶掉关键词后静默落到商务槽
    title = _match(SCORE_CHAPTER_RULES, blob, "商务标")
    form = _match(SCORE_FORM_RULES, blob, "text")
    mats = s_item.get("required_materials") or ""
    notes = "%s（%s分）" % (item or "（评分项事项未载明）",
                           int(pts) if pts == int(pts) else pts)
    if mats:
        notes = "%s；依据材料：%s" % (notes, mats)
    return {
        "source_type": "scoring", "source_ref": sid,
        "chapter_id": _anchor_or_raise(title, "评分卡 %s" % sid), "response_form": form,
        "word_target": max(300, round(pts * 350)),
        "required_facts": facts, "owner": "",
        "status": "blocked_by_facts", "notes": notes,
    }


def derive_business_card(form):
    """03c 单表 → 商务表任务卡 dict（notes 含表名/必填字段/签章——
    ④ index_evidence 的证据文件名关键词匹配面；零金额口径由 03c 保证）。"""
    fid = form.get("id") or ""
    name = str(form.get("name") or "")
    fields = form.get("required_fields") or []
    seal = str(form.get("seal") or "")
    blob = "%s %s" % (name, "、".join(str(f) for f in fields))
    facts = _derive_required_facts(blob)
    hint_form, hint_wt = FORM_HINT.get(fid, ("table", 600))
    fields_str = "、".join(str(f) for f in fields) or "（框架表，无固定必填字段）"
    notes = "%s：必填 %s；签章：%s" % (name, fields_str, seal)
    return {
        "source_type": "business", "source_ref": fid,
        "chapter_id": form.get("chapter_id") or _anchor_or_raise(
            FALLBACK_CHAPTER, "商务表 %s「%s」" % (fid, name)),
        "response_form": hint_form, "word_target": hint_wt,
        "required_facts": facts, "owner": "",
        "status": "blocked_by_facts" if facts else "ready", "notes": notes,
    }


def load_json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def build_03(meta, facts):
    """序列化 03_bid-plan.json（契约 0.2，assets/bid-plan.schema.json）。

    卡序：条款卡（按 01.clauses 数组序）→ 商务表卡（bf-01..24）→
    评分卡（按 01.scoring.items 数组序）；id 顺序编发 t-%04d。
    coverage 按评分卡 source_ref 与 01.scoring.items 真实对账。
    """
    clauses = facts.get("clauses") or []
    s_items = facts.get("scoring", {}).get("items", [])
    # 商务表卡直接镜像 03c 结构（BUSINESS_FORMS 常量 → build_03c 同源字段）；
    # 挂接先过显式校验（章节标题/表名两跳命中 + 一章一表），解析同源
    # resolve_form_chapter（锚定上下文随链内 set_chapter_context 走）
    validate_forms_chapter_linkage()
    forms = [
        {"id": fid, "name": name,
         "chapter_id": resolve_form_chapter(fid, name, chap),
         "required_fields": rf, "seal": seal}
        for (fid, name, chap, rf, seal, _copies) in BUSINESS_FORMS
    ]
    derived = ([derive_clause_card(c) for c in clauses]
               + [derive_business_card(fm) for fm in forms]
               + [derive_scoring_card(s) for s in s_items])
    items = []
    for seq, card in enumerate(derived, start=1):
        card = dict(card)
        card["id"] = "t-%04d" % seq
        items.append(card)
    score_ids = [str(s.get("id") or "") for s in s_items]
    card_refs = {it["source_ref"] for it in items if it["source_type"] == "scoring"}
    mapped = sum(1 for sid in score_ids if sid in card_refs)
    unmapped = [sid for sid in score_ids if sid not in card_refs]
    return {
        "schema_version": "0.2",
        "preconditions": [{
            "id": "p-0001", "item": "补遗/澄清文件对照",
            "result": "unknown",
            "evidence": "本次未提供补遗/澄清文件，无法逐份核对",
            "blocking": True,
        }],
        "items": items,
        "coverage": {
            "scoring_total": len(s_items), "mapped": mapped, "unmapped": unmapped,
        },
    }


def build_04(plan, chapters=None):
    """序列化 04_outline.json（契约 0.1，assets/outline.schema.json）。

    计划书 §6.2 D4 修正字段集：id/number/title 逐字取自 01c；
    order/parent/depends_on/word_target/scoring_refs/status/notes 为套件派生。
    只记结构与位置，不含任何金额；评分点落点不得改动招标章名（铁律 2），
    评分点与章名的冲突写节点 notes（M3）。

    chapters：01c 章节树（v0.26.0 起须传 build_bid_plan 同一来源——派生/兜底
    与 01c 保持同源，防止 04 与 01c 章节树漂移）；None 时回落常量兜底
    （独立用法，链内禁用该路径）。
    """
    chapters_01c = chapters if chapters is not None else build_01c(warn=False)["chapters"]
    # 父节点推导：level 2 为顶层（parent=null），子节点指向最近的上层节点
    parent = {}
    stack = {}  # level -> 该层最近一次出现的章节 id
    for c in chapters_01c:
        lv = c["level"]
        parent[c["id"]] = stack.get(lv - 1)
        stack = {k: v for k, v in stack.items() if k < lv}
        stack[lv] = c["id"]
    # 篇幅预算：该章下任务卡 word_target 合计（非金额、非页数）
    wt_sum = {}
    refs = {}
    for it in plan["items"]:
        cid = it["chapter_id"]
        wt_sum[cid] = wt_sum.get(cid, 0) + it.get("word_target", 0)
        if it["source_ref"].startswith("S-") or it["source_ref"].startswith("T"):
            refs.setdefault(cid, []).append(it["source_ref"])
    outline_chapters = []
    for order, c in enumerate(chapters_01c, start=1):
        outline_chapters.append({
            "id": c["id"], "number": c["number"], "title": c["title"],
            "order": order, "parent": parent[c["id"]],
            "depends_on": [], "word_target": wt_sum.get(c["id"], 0),
            "scoring_refs": refs.get(c["id"], []),
            "status": "pending", "notes": "",
        })
    return {
        "schema_version": "0.1",
        "chapters": outline_chapters,
    }


def build_gap_md(plan):
    """素材缺口清单（① 附属人读产物，随 03 一并落盘）。

    v0.24.0 起全部内容从 03 任务卡派生：待录入类别按 required_facts 前缀
    归类、待澄清项按 blocked_by_clarify 卡逐条列出——不再内嵌示例项目
    的澄清清单（招标方澄清待补什么，由 01 条款 value_state 决定）。
    """
    items = plan["items"]
    clar = [it for it in items if it["status"] == "blocked_by_clarify"]
    fact_missing = sorted({f for it in items for f in it["required_facts"]})
    cat_names = {"qual": "资质", "perf": "业绩", "pers": "人员",
                 "fin": "财务", "eq": "设备"}
    by_cat = {}
    for f in fact_missing:
        prefix = str(f).split("-", 1)[0]
        by_cat.setdefault(cat_names.get(prefix, prefix), []).append(f)
    gap_md = ["# 素材缺口清单（① v0.24.0 产出）", ""]
    gap_md.append("> 生成依据：00_metadata.json(stage=reviewed) + 01_tender-facts.json(0.4)。状态含义：ready=无需事实库/可立即编制；blocked_by_facts=事实库缺对应条目；blocked_by_clarify=须投标截止前取得书面澄清并固化。")
    gap_md.append("")
    gap_md.append("## 一、待澄清（blocked_by_clarify，须投标前书面确认）")
    if clar:
        for it in clar:
            gap_md.append("- [%s] %s：%s" % (it["source_ref"], it["id"], it["notes"]))
    else:
        gap_md.append("- （无）")
    gap_md.append("")
    gap_md.append("## 二、事实库缺口（blocked_by_facts，须录入 02_facts 后重跑）")
    gap_md.append("- 所需事实 id：%s" % ("、".join(fact_missing) if fact_missing else "（无）"))
    if by_cat:
        segs = ["%s(%s)" % (c, "、".join(ids)) for c, ids in sorted(by_cat.items())]
        gap_md.append("- 待录入类别：%s" % "；".join(segs))
    else:
        gap_md.append("- 待录入类别：（无）")
    gap_md.append("- 补遗/澄清文件：本次未提供，p-0001 结果 unknown（阻断），投标前须以最新补遗为准")
    gap_md.append("")
    gap_md.append("## 三、阻断级前置（preconditions）")
    gap_md.append("- p-0001 补遗/澄清文件对照：result=unknown / blocking=true → 未对照不得交 G1")
    gap_md.append("")
    gap_md.append("## 四、统计")
    gap_md.append("- 任务卡总数：%d（scoring=%d, waste=%d, qualification=%d, business=%d）" % (
        len(items),
        sum(1 for x in items if x["source_type"] == "scoring"),
        sum(1 for x in items if x["source_type"] == "waste"),
        sum(1 for x in items if x["source_type"] == "qualification"),
        sum(1 for x in items if x["source_type"] == "business")))
    cov = plan["coverage"]
    gap_md.append("- coverage：scoring_total=%d, mapped=%d, unmapped=%s（必须为空才可交 G1）"
                  % (cov["scoring_total"], cov["mapped"], cov["unmapped"]))
    return "\n".join(gap_md)


def main():
    ap = argparse.ArgumentParser(description="生成 03_bid-plan.json / 04_outline.json / 素材缺口清单.md")
    ap.add_argument("--bid", required=True, help="项目 bid 目录")
    args = ap.parse_args()
    meta = load_json(os.path.join(args.bid, "00_metadata.json"))
    facts = load_json(os.path.join(args.bid, "01_tender-facts.json"))
    assert meta.get("stage") == "reviewed", "stage 必须为 reviewed"
    assert facts.get("contract_schema_version") == "0.4", "facts 契约必须为 0.4"

    c03 = build_03(meta, facts)
    c04 = build_04(c03)
    with open(os.path.join(args.bid, "03_bid-plan.json"), "w", encoding="utf-8") as f:
        json.dump(c03, f, ensure_ascii=False, indent=2)
    with open(os.path.join(args.bid, "04_outline.json"), "w", encoding="utf-8") as f:
        json.dump(c04, f, ensure_ascii=False, indent=2)
    with open(os.path.join(args.bid, "素材缺口清单.md"), "w", encoding="utf-8") as f:
        f.write(build_gap_md(c03))
    cov = c03["coverage"]
    n_cl = sum(1 for x in c03["items"] if str(x["source_ref"]).startswith("c-"))
    n_bf = sum(1 for x in c03["items"] if str(x["source_ref"]).startswith("bf-"))
    n_sc = sum(1 for x in c03["items"] if x["source_type"] == "scoring")
    print("OK 任务卡 %d 张（条款 %d＋商务表 %d＋评分 %d）；coverage: total=%d mapped=%d unmapped=%d"
          % (len(c03["items"]), n_cl, n_bf, n_sc,
             cov["scoring_total"], cov["mapped"], len(cov["unmapped"])))
    print("OK", os.path.join(args.bid, "03_bid-plan.json"))
    print("OK", os.path.join(args.bid, "04_outline.json"))
    print("OK", os.path.join(args.bid, "素材缺口清单.md"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
