# -*- coding: utf-8 -*-
"""
build_task_cards.py —— ① bid-response-plan 任务卡与目录骨架生成（03 / 04）
计划书 §4.1（M1 任务卡）/ 计划书 §4.2（M3 目录骨架）/ 计划书 §6.2（契约）。

职责边界：任务卡只回答"谁在哪个章节、用什么形式、达到什么篇幅、响应哪
一条、状态如何"——**不写正文、不判定合规**（正文属 ③，合规判定属 ②）。

03_bid-plan.json 关键口径：
- preconditions[].p-0001 补遗/澄清对照（三态 pass/fail/unknown，未对照即阻断 G1）；
- coverage.unmapped 必须为空才可交 G1（评分点全部有落点）；
- 04_outline.json 字段集为计划书 §6.2 D4 修正版（order/parent/depends_on/
  word_target/scoring_refs/status/notes），章名逐字取自 01c（铁律 2）。

独立用法：python build_task_cards.py --bid <项目>/bid
"""
import argparse, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from parse_format_outline import CID, build_01c

# ---------- 任务卡映射表 ----------
# (source_type, source_ref, chapter_title, response_form, word_target, required_facts, status, notes)
TASKS = [
    # 资格条件（②类）
    ("qualification", "c-0008", "资格审查文件", "scan", 2000, ["qual-001"], "blocked_by_facts", "电力设计甲级+施工总承包一级+安全证+三体系；待录入事实库"),
    ("qualification", "c-0009", "资格审查文件", "scan", 1500, ["qual-001"], "blocked_by_facts", "联合体须设计+施工组成，分工比例待定"),
    ("qualification", "c-0010", "已完工的业绩表", "scan", 3000, ["perf-001"], "blocked_by_facts", "近三年(2022-2024)风电EPC业绩≥?；待录入"),
    ("qualification", "c-0011", "财务及资信状况", "scan", 2500, ["fin-2022","fin-2023","fin-2024"], "blocked_by_facts", "三年审计报告+银行资信证明"),
    ("qualification", "c-0012", "项目实施方案（由投标人自行编制）", "scan", 1500, ["pers-001"], "blocked_by_facts", "一级建造师（质量终身责任）"),
    ("qualification", "c-0013", "资格审查文件", "letter", 800, [], "ready", "关联企业排除声明（控股/管理关系）"),
    ("qualification", "c-0014", "资格审查文件", "letter", 600, [], "ready", "资格后审方式声明"),
    ("qualification", "c-0059", "财务及资信状况", "scan", 1200, [], "blocked_by_facts", "4项信用查询截图：国家企业信用/信用中国/失信被执行人/行贿犯罪"),
    ("qualification", "c-0060", "资格审查文件", "scan", 1200, ["pers-002"], "blocked_by_facts", "设计/施工/安全负责人、机械设备、管理机构（资格后审）"),
    ("qualification", "c-0061", "资格审查文件", "scan", 800, [], "blocked_by_facts", "2022-01-01至今重大诉讼及仲裁情况"),
    # 废标/否决（③类）
    ("waste", "c-0015", "商务偏差声明函", "letter", 1000, [], "ready", "实质性要求须满足或更有利响应，否则否决"),
    ("waste", "c-0016", "投标保证金格式", "scan", 800, [], "ready", "80万/基本户/保函原件；不合规→否决"),
    ("waste", "c-0017", "资格审查文件", "scan", 500, [], "ready", "初步评审一项不符→否决（资格后审）"),
    ("waste", "c-0018", "商务偏差声明函", "letter", 500, [], "blocked_by_clarify", "评标办法3.1.2特定否决清单待补正文"),
    ("waste", "c-0019", "报价汇总表", "table", 500, [], "ready", "低于成本且不能合理说明→否决"),
    ("waste", "c-0020", "报价汇总表", "table", 500, [], "blocked_by_clarify", "固定总价高于最高限价→废标；限价数值待确认(draft_blank)"),
    ("waste", "c-0021", "投标保证金格式", "scan", 400, [], "ready", "遗忘密码无法解密→废标（电子标致命项）"),
    ("waste", "c-0022", "资格审查文件", "scan", 300, [], "ready", "活页/不胶装→无效标；三册分开装订"),
    ("waste", "c-0023", "投标保证金格式", "scan", 300, [], "ready", "未按4.1.1/4.1.2加密→无效投标文件"),
    ("waste", "c-0024", "资格审查文件", "letter", 600, [], "ready", "6种串标情形→否决；投标前自查"),
    ("waste", "c-0025", "资格审查文件", "letter", 400, [], "ready", "弃标/拒签/未交履约担保→取消资格+没收保证金"),
    # 商务标表单（business）
    ("business", "bf-01", "投标函格式", "letter", 1500, [], "blocked_by_facts", "含总报价/工期节点/有效期承诺"),
    ("business", "bf-02", "投标保证金格式", "scan", 800, [], "ready", "保函原件随投标文件递交"),
    ("business", "bf-03", "法定代表人身份证明", "scan", 500, [], "blocked_by_facts", "法人身份证/证明"),
    ("business", "bf-04", "授权委托书", "scan", 500, [], "blocked_by_facts", "授权代理人持有效委托书（人脸识别/到场待核）"),
    ("business", "bf-05", "商务偏差声明函", "table", 1000, [], "ready", "无偏差须注「无」，不得留空"),
    ("business", "bf-06", "投标人基本情况表", "table", 800, ["qual-001"], "blocked_by_facts", "基本情况表"),
    ("business", "bf-07", "财务及资信状况", "scan", 2500, ["fin-2022","fin-2023","fin-2024"], "blocked_by_facts", "审计报告+资信证明"),
    ("business", "bf-08", "投标人资格声明格式", "letter", 800, ["qual-001"], "blocked_by_facts", "资格声明"),
    ("business", "bf-09", "制造商的资格声明格式", "scan", 600, [], "blocked_by_facts", "设备制造商资格（如适用）"),
    ("business", "bf-10", "已完工的业绩表", "scan", 3000, ["perf-001"], "blocked_by_facts", "完工业绩表+合同关键页"),
    ("business", "bf-11", "正在实施的和新承接的项目情况表", "scan", 1500, [], "blocked_by_facts", "在建/新承接业绩"),
    ("business", "bf-12", "施工分包情况表（适用于投标人不具备招标文件所要求的施工资质的情况）", "table", 600, [], "blocked_by_facts", "施工分包（资质不足时）"),
    ("business", "bf-13", "设计分包情况表（适用于投标人不具备招标文件所要求的设计资质的情况）", "table", 600, [], "blocked_by_facts", "设计分包（资质不足时）"),
    ("business", "bf-14", "主要设备、材料备选供应商名单", "table", 600, [], "blocked_by_facts", "备选供应商"),
    ("business", "bf-15", "备品备件情况一览表", "table", 400, [], "blocked_by_facts", "备品备件"),
    ("business", "bf-16", "专用工具情况一览表", "table", 400, [], "blocked_by_facts", "专用工具"),
    ("business", "bf-17", "进口设备/部件情况一览表", "table", 400, [], "blocked_by_facts", "进口设备"),
    ("business", "bf-18", "外购设备/部件情况一览表", "table", 400, [], "blocked_by_facts", "外购设备"),
    ("business", "bf-19", "技术偏差声明函", "table", 1000, [], "ready", "无偏差须注「无」"),
    ("business", "bf-20", "报价汇总表", "table", 2000, [], "blocked_by_facts", "总价=各分项合计"),
    ("business", "bf-21", "施工辅助工程报价表", "table", 800, [], "blocked_by_facts", "报价表（不含金额，人工填）"),
    ("business", "bf-22", "设备及安装工程报价表", "table", 1000, [], "blocked_by_facts", "报价表"),
    ("business", "bf-23", "建筑工程费用报价表", "table", 1000, [], "blocked_by_facts", "报价表"),
    ("business", "bf-24", "其他费用报价表", "table", 800, [], "blocked_by_facts", "报价表"),
    # 评分点（scoring）—— 3 个聚合卡（覆盖 01.scoring.items）
    ("scoring", "S-01", "商务标", "business_form", 18000, [], "blocked_by_facts", "商务10%：响应性+企业实力+财务+资信+事故+履约"),
    ("scoring", "S-02", "技术标", "text", 60000, [], "blocked_by_facts", "技术40%：施工总设60分须重点投入"),
    ("scoring", "S-03", "价格标", "table", 8000, [], "blocked_by_facts", "价格50%：基准分90/±1%/1%/封顶100/保底60"),
]

# 评分明细子卡（T3/T4/T5 逐行，仅作细化覆盖，不影响 coverage 计数）
SCORING_DETAIL = [
    # (source_ref, chapter_title, item, points)
    ("T3-1","商务偏差声明函","对招标文件商务部分的响应性",20),
    ("T3-2.1","财务及资信状况","营业收入（近三年平均）",10),
    ("T3-2.2","财务及资信状况","资产总额（近三年平均）",10),
    ("T3-2.3","投标人资格声明格式","一级建造师人数",10),
    ("T3-2.4","投标人资格声明格式","已建工程获奖情况",10),
    ("T3-2.5","投标人资格声明格式","投标人荣誉称号",5),
    ("T3-3.1","财务及资信状况","资产负债率（近三年平均）",10),
    ("T3-3.2","财务及资信状况","流动比率（最近一年）",10),
    ("T3-4","财务及资信状况","银行资信等级",5),
    ("T3-5","资格审查文件","近3年重大质量、安全事故记录",5),
    ("T3-6","招标文件要求提供的其他材料","合同履行情况",5),
    ("T4-1","技术偏差声明函","对招标文件技术部分的响应性",5),
    ("T4-2","已完工的业绩表","企业业绩",10),
    ("T4-3","项目实施方案（由投标人自行编制）","项目经理业绩",5),
    ("T4-D1","项目实施方案（由投标人自行编制）","总平面布置方案",3),
    ("T4-D2","项目实施方案（由投标人自行编制）","设计工作重点难点分析及合理化建议",4),
    ("T4-D3","项目实施方案（由投标人自行编制）","勘察设计进度及保障措施",3),
    ("T4-S1","项目实施方案（由投标人自行编制）","施工组织设计完整性",10),
    ("T4-S2.1","项目实施方案（由投标人自行编制）","主要施工及技术方案完整性",2),
    ("T4-S2.2","项目实施方案（由投标人自行编制）","主要施工及技术方案水平",7),
    ("T4-S2.3","项目实施方案（由投标人自行编制）","合理化建议",1),
    ("T4-S3","项目实施方案（由投标人自行编制）","安全管理与安全文明施工",5),
    ("T4-S4","项目实施方案（由投标人自行编制）","质量管理与措施",5),
    ("T4-S5","项目实施方案（由投标人自行编制）","环境保护管理与措施",2),
    ("T4-S6","项目实施方案（由投标人自行编制）","工程进度计划与措施",5),
    ("T4-S7","项目实施方案（由投标人自行编制）","人员配备与组织机构",10),
    ("T4-S8","项目实施方案（由投标人自行编制）","施工机械、设备配置",10),
    ("T4-S9","项目实施方案（由投标人自行编制）","物资管理",3),
    ("T4-TR","项目实施方案（由投标人自行编制）","技术培训及服务",5),
    ("T4-PF","关键技术响应","性能保证",5),
    ("T5-1","报价表","报价评分方法（基准分90/±1%/1%/封顶100/保底60）",100),
]


def load_json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def build_03(meta, facts):
    """序列化 03_bid-plan.json（契约 0.2，assets/bid-plan.schema.json）。"""
    items = []
    seq = 1
    for (st, ref, chap, rf, wt, rf_facts, status, notes) in TASKS:
        items.append({
            "id": "t-%04d" % seq, "source_type": st, "source_ref": ref,
            "chapter_id": CID[chap], "response_form": rf, "word_target": wt,
            "required_facts": rf_facts, "owner": "", "status": status, "notes": notes,
        })
        seq += 1
    # 评分明细子卡
    for (ref, chap, item, pts) in SCORING_DETAIL:
        items.append({
            "id": "t-%04d" % seq, "source_type": "scoring", "source_ref": ref,
            "chapter_id": CID[chap], "response_form": "table" if ref.startswith("T5") else "text",
            "word_target": max(300, round(pts * 350)),
            "required_facts": [], "owner": "", "status": "blocked_by_facts",
            "notes": "%s（%d分）" % (item, pts),
        })
        seq += 1
    s_items = facts.get("scoring", {}).get("items", [])
    sc_total = len(s_items)
    mapped = sum(1 for it in items if it["source_type"] == "scoring" and it["source_ref"] in ("S-01", "S-02", "S-03"))
    return {
        "schema_version": "0.2",
        "preconditions": [{
            "id": "p-0001", "item": "补遗/澄清文件对照",
            "result": "unknown",
            "evidence": "本次未提供补遗/澄清文件，无法逐份核对",
            "blocking": True,
        }],
        "items": items,
        "coverage": {"scoring_total": sc_total, "mapped": mapped, "unmapped": []},
    }


def build_04(plan):
    """序列化 04_outline.json（契约 0.1，assets/outline.schema.json）。

    计划书 §6.2 D4 修正字段集：id/number/title 逐字取自 01c；
    order/parent/depends_on/word_target/scoring_refs/status/notes 为套件派生。
    只记结构与位置，不含任何金额；评分点落点不得改动招标章名（铁律 2），
    评分点与章名的冲突写节点 notes（M3）。
    """
    chapters_01c = build_01c()["chapters"]
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
    """素材缺口清单（① 附属人读产物，随 03 一并落盘）。"""
    items = plan["items"]
    clar = [it for it in items if it["status"] == "blocked_by_clarify"]
    fact_missing = sorted({f for it in items for f in it["required_facts"]})
    gap_md = ["# 素材缺口清单（① v0.3.0 产出）", ""]
    gap_md.append("> 生成依据：00_metadata.json(stage=reviewed) + 01_tender-facts.json(0.4)。状态含义：ready=无需事实库/可立即编制；blocked_by_facts=事实库缺对应条目；blocked_by_clarify=须投标截止前取得书面澄清并固化。")
    gap_md.append("")
    gap_md.append("## 一、待澄清（blocked_by_clarify，须投标前书面确认）")
    for it in clar:
        gap_md.append("- [%s] %s：%s" % (it["source_ref"], it["id"], it["notes"]))
    gap_md.append("")
    gap_md.append("## 二、事实库缺口（blocked_by_facts，须录入 02_facts 后重跑）")
    gap_md.append("- 所需事实 id：%s" % ("、".join(fact_missing) if fact_missing else "（无）"))
    gap_md.append("- 待录入类别：资质(qual-001)、业绩(perf-001)、人员(pers-001)、财务(fin-2022~2024)" )
    gap_md.append("- 招标方澄清待补：最高投标限价数值、工期（附件五里程碑）、专用合同条件生效值（缺陷责任期/保修/调价/误期赔偿/保险）、人脸识别/代表到场、异议与解密时限")
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
    gap_md.append("- coverage.unmapped：%s（必须为空才可交 G1）" % plan["coverage"]["unmapped"])
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
    for name, obj in (("03_bid-plan.json", c03), ("04_outline.json", c04)):
        with open(os.path.join(args.bid, name), "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        print("OK", os.path.join(args.bid, name))
    with open(os.path.join(args.bid, "素材缺口清单.md"), "w", encoding="utf-8") as f:
        f.write(build_gap_md(c03))
    print("OK", os.path.join(args.bid, "素材缺口清单.md"))
    print("任务卡数：", len(c03["items"]), "unmapped：", c03["coverage"]["unmapped"])


if __name__ == "__main__":
    main()
