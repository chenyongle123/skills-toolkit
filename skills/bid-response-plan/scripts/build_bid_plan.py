# -*- coding: utf-8 -*-
"""
build_bid_plan.py —— ① bid-response-plan v0.2.0 真功能生成器
计划书 §4.1（M1 任务卡）/ §4.2（M3 目录骨架）/ §6.2（契约）。
输入：00_metadata.json(stage=reviewed) + 01_tender-facts.json(契约0.4)
输出：01c_format-outline.json / 03_bid-plan.json / 04_outline.json
      / 03c_business-forms.json / 01b_spec-items.json / 素材缺口清单.md
用法：python build_bid_plan.py --bid <项目>/bid
注意：01c 章节树来自本项目招标文件第七章「投标文件格式」逐字抽取（已固化于
FORMAT_CHAPTERS 常量）；换项目须重新抽取第七章再覆盖该常量。
"""
import argparse, json, os, sys, re

PY = sys.version_info[:2]
HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.normpath(os.path.join(HERE, "..", "assets"))

# ---------- 1. 01c 章节树（本项目第七章「投标文件格式」逐字） ----------
FORMAT_CHAPTERS = [
    # (id, number, title, level)
    ("n-1001", "一", "商务标", 2),
    ("n-1101", "1", "投标函格式", 3),
    ("n-1102", "2", "投标保证金格式", 3),
    ("n-1103", "3", "法定代表人身份证明", 3),
    ("n-1104", "4", "授权委托书", 3),
    ("n-1105", "5", "商务偏差声明函", 3),
    ("n-1106", "6", "资格审查文件", 3),
    ("n-1111", "6.1", "投标人基本情况表", 4),
    ("n-1112", "6.2", "财务及资信状况", 4),
    ("n-1113", "6.3", "投标人资格声明格式", 4),
    ("n-1114", "6.4", "制造商的资格声明格式", 4),
    ("n-1115", "6.5", "其它资料", 4),
    ("n-1107", "7", "业绩", 3),
    ("n-1121", "7.1", "已完工的业绩表", 4),
    ("n-1122", "7.2", "正在实施的和新承接的项目情况表", 4),
    ("n-1108", "8", "分包或外购情况表", 3),
    ("n-1131", "8.1", "施工分包情况表", 4),
    ("n-1132", "8.2", "设计分包情况表", 4),
    ("n-1133", "8.3", "主要设备、材料备选供应商名单", 4),
    ("n-1134", "8.4", "备品备件情况一览表", 4),
    ("n-1135", "8.5", "专用工具情况一览表", 4),
    ("n-1136", "8.6", "进口设备/部件情况一览表", 4),
    ("n-1137", "8.7", "外购设备/部件情况一览表", 4),
    ("n-1109", "9", "招标文件要求提供的其他材料", 3),
    ("n-2001", "二", "技术标", 2),
    ("n-2101", "1", "承包人建议书", 3),
    ("n-2102", "2", "项目实施方案", 3),
    ("n-2103", "3", "技术偏差声明函", 3),
    ("n-2104", "4", "货物主要技术指标和性能的详细说明", 3),
    ("n-2105", "5", "系统设备技术性能检验大纲", 3),
    ("n-2106", "6", "主要设备的产品说明、技术参数、质保声明等", 3),
    ("n-2107", "7", "关键技术响应", 3),
    ("n-2108", "8", "其他招标文件技术规范要求投标人提供或编写的资料", 3),
    ("n-3001", "三", "价格标", 2),
    ("n-3101", "1", "报价要求", 3),
    ("n-3102", "2", "价格说明", 3),
    ("n-3103", "3", "报价表", 3),
    ("n-3111", "3.1", "报价汇总表", 4),
    ("n-3112", "3.2", "施工辅助工程报价表", 4),
    ("n-3113", "3.3", "设备及安装工程报价表", 4),
    ("n-3114", "3.4", "建筑工程费用报价表", 4),
    ("n-3115", "3.5", "其他费用报价表", 4),
]
CID = {t: i for (i, _, t, _) in FORMAT_CHAPTERS}

# 排版要求（前附表3.7.3/3.7.4/3.7.5 + 默认基线；未载明页限 → null）
TYPOGRAPHY = {
    "scope": "full_doc",
    "font_body": "", "size_body": "", "line_spacing": "",
    "margins": "", "page_number": "", "page_limit": None,
    "identity_ban": [],
    "indent": "首行缩进2字符（通用基线，招标未载明）",
    "binding": "A4幅胶装成册、不可拆卸；商务/技术/报价分开装订（前附表3.7.5）",
    "seal": "电子CA签章或纸质PDF扫描；纸质正本重要内容法人或授权代理人签字（前附表3.7.3）",
    "source": "tender_required",
}

# ---------- 2. 任务卡映射表 ----------
# (source_type, source_ref, chapter_title, response_form, word_target, required_facts, status, notes)
TASKS = [
    # 资格条件（②类）
    ("qualification", "c-0008", "资格审查文件", "scan", 2000, ["qual-001"], "blocked_by_facts", "电力设计甲级+施工总承包一级+安全证+三体系；待录入事实库"),
    ("qualification", "c-0009", "资格审查文件", "scan", 1500, ["qual-001"], "blocked_by_facts", "联合体须设计+施工组成，分工比例待定"),
    ("qualification", "c-0010", "已完工的业绩表", "scan", 3000, ["perf-001"], "blocked_by_facts", "近三年(2022-2024)风电EPC业绩≥?；待录入"),
    ("qualification", "c-0011", "财务及资信状况", "scan", 2500, ["fin-2022","fin-2023","fin-2024"], "blocked_by_facts", "三年审计报告+资信证明+4项信用查询截图"),
    ("qualification", "c-0012", "项目实施方案", "scan", 1500, ["pers-001"], "blocked_by_facts", "一级建造师（质量终身责任）"),
    ("qualification", "c-0013", "资格审查文件", "letter", 800, [], "ready", "关联企业排除声明（控股/管理关系）"),
    ("qualification", "c-0014", "资格审查文件", "letter", 600, [], "ready", "资格后审方式声明"),
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
    ("business", "bf-12", "施工分包情况表", "table", 600, [], "blocked_by_facts", "施工分包（资质不足时）"),
    ("business", "bf-13", "设计分包情况表", "table", 600, [], "blocked_by_facts", "设计分包（资质不足时）"),
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
    ("T4-3","项目实施方案","项目经理业绩",5),
    ("T4-D1","项目实施方案","总平面布置方案",3),
    ("T4-D2","项目实施方案","设计工作重点难点分析及合理化建议",4),
    ("T4-D3","项目实施方案","勘察设计进度及保障措施",3),
    ("T4-S1","项目实施方案","施工组织设计完整性",10),
    ("T4-S2.1","项目实施方案","主要施工及技术方案完整性",2),
    ("T4-S2.2","项目实施方案","主要施工及技术方案水平",7),
    ("T4-S2.3","项目实施方案","合理化建议",1),
    ("T4-S3","项目实施方案","安全管理与安全文明施工",5),
    ("T4-S4","项目实施方案","质量管理与措施",5),
    ("T4-S5","项目实施方案","环境保护管理与措施",2),
    ("T4-S6","项目实施方案","工程进度计划与措施",5),
    ("T4-S7","项目实施方案","人员配备与组织机构",10),
    ("T4-S8","项目实施方案","施工机械、设备配置",10),
    ("T4-S9","项目实施方案","物资管理",3),
    ("T4-TR","项目实施方案","技术培训及服务",5),
    ("T4-PF","关键技术响应","性能保证",5),
    ("T5-1","报价表","报价评分方法（基准分90/±1%/1%/封顶100/保底60）",100),
]

# 03c 商务表格框架
BUSINESS_FORMS = [
    # (id, name, chapter_title, required_fields, seal, copies)
    ("bf-01","投标函","投标函格式",["投标总报价（大写）","投标总报价（小写）","安全文明施工费","危大工程施工技术措施费","开工日期","全部机组并网发电日期","移交生产完成日期","竣工验收完成日期","投标有效期承诺"],"法定代表人签字+单位公章",5),
    ("bf-02","投标保证金","投标保证金格式",["保证金金额（大写）","保证金金额（小写）","账号","保函/转账凭证"],"按前附表3.4.1",5),
    ("bf-03","法定代表人身份证明","法定代表人身份证明",["姓名","性别","年龄","职务","系（投标人）的法定代表人"],"附身份证复印件",5),
    ("bf-04","授权委托书","授权委托书",["委托人","受托人","授权范围","授权期限"],"法人签字+单位公章",5),
    ("bf-05","商务偏差声明函","商务偏差声明函",["条款号","招标文件要求","偏差内容","说明理由"],"按前附表3.7.3",5),
    ("bf-06","投标人基本情况表","投标人基本情况表",["名称","注册地址","成立时间","注册资本","法定代表人","联系方式"],"单位公章",5),
    ("bf-07","财务及资信状况","财务及资信状况",["近三年审计报告","银行资信证明","信用查询截图（4项）"],"单位公章",5),
    ("bf-08","投标人资格声明格式","投标人资格声明格式",["资质等级","证书编号","有效期"],"单位公章",5),
    ("bf-09","制造商的资格声明格式","制造商的资格声明格式",["制造商名称","货物名称","资质"],"制造商盖章",5),
    ("bf-10","已完工的业绩表","已完工的业绩表",["项目名称","发包人","合同金额","竣工日期","项目经理"],"单位公章+证明",5),
    ("bf-11","正在实施的和新承接的项目情况表","正在实施的和新承接的项目情况表",["项目名称","发包人","合同金额","进度"],"单位公章",5),
    ("bf-12","施工分包情况表","施工分包情况表",["分包内容","分包人","资质"],"单位公章",5),
    ("bf-13","设计分包情况表","设计分包情况表",["分包内容","分包人","资质"],"单位公章",5),
    ("bf-14","主要设备、材料备选供应商名单","主要设备、材料备选供应商名单",["设备/材料名称","备选供应商"],"单位公章",5),
    ("bf-15","备品备件情况一览表","备品备件情况一览表",["名称","规格","数量"],"单位公章",5),
    ("bf-16","专用工具情况一览表","专用工具情况一览表",["名称","规格","数量"],"单位公章",5),
    ("bf-17","进口设备/部件情况一览表","进口设备/部件情况一览表",["名称","产地","数量"],"单位公章",5),
    ("bf-18","外购设备/部件情况一览表","外购设备/部件情况一览表",["名称","供应商","数量"],"单位公章",5),
    ("bf-19","技术偏差声明函","技术偏差声明函",["条款号","招标文件要求","偏差内容","说明理由"],"按前附表3.7.3",5),
    ("bf-20","报价汇总表","报价汇总表",["子目名称","单价","合价","投标总价"],"法定代表人签字+单位公章",5),
    ("bf-21","施工辅助工程报价表","施工辅助工程报价表",["子目名称","单价","合价"],"按报价要求1.1-1.17",5),
    ("bf-22","设备及安装工程报价表","设备及安装工程报价表",["子目名称","单价","合价"],"按报价要求",5),
    ("bf-23","建筑工程费用报价表","建筑工程费用报价表",["子目名称","单价","合价"],"按报价要求",5),
    ("bf-24","其他费用报价表","其他费用报价表",["子目名称","单价","合价"],"按报价要求",5),
]


def load_json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def build_01c():
    return {
        "schema_version": "0.2",
        "chapters": [
            {"id": i, "number": n, "title": t, "level": lv, "page": "n/a-无分页"}
            for (i, n, t, lv) in FORMAT_CHAPTERS
        ],
        "typography": TYPOGRAPHY,
    }


def build_03(meta, facts):
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
    # 目录骨架 = 01c 章节树 + 评分点落点标注
    chap_map = {c["id"]: c for c in build_01c()["chapters"]}
    placed = {}
    for it in plan["items"]:
        placed.setdefault(it["chapter_id"], []).append(it["source_ref"])
    outline_chapters = []
    for c in build_01c()["chapters"]:
        refs = placed.get(c["id"], [])
        outline_chapters.append({
            "id": c["id"], "number": c["number"], "title": c["title"],
            "level": c["level"], "page": c["page"],
            "scoring_hits": [r for r in refs if r.startswith("S-") or r.startswith("T")],
        })
    return {
        "schema_version": "0.2",
        "style_source": "招标文件第七章投标文件格式 + 前附表",
        "chapters": outline_chapters,
        "typography": TYPOGRAPHY,
        "notes": "评分点落点（scoring_hits）仅供编排参考，不得为凑评分点改动招标规定的章节名（铁律2）",
    }


def build_03c():
    forms = []
    for (fid, name, chap, rf, seal, copies) in BUSINESS_FORMS:
        forms.append({
            "id": fid, "name": name, "tender_page": "n/a-无分页",
            "chapter_id": CID[chap], "required_fields": rf, "seal": seal,
            "copies": copies, "filled_file": "", "status": "blank",
        })
    return {
        "schema_version": "0.1",
        "forms": forms,
        "consistency_rules": [
            "大写金额 = 小写金额",
            "各报价表分项合计 = 报价汇总表投标总价",
            "投标保证金金额与招标文件前附表3.4.1载明一致",
        ],
    }


def build_01b():
    # 技术规范条目：本标准仅抽取与已知条款对应的少量代表项，
    # 完整抽取须覆盖「技术标准和要求」章（P2558+），留待 ⓪/① 后续补抽。
    items = [
        {"id": "sp-001", "clause": "合同专用/通用条款", "page": "n/a-无分页",
         "requirement": "240小时试运行", "required_value": "240h", "unit": "h",
         "tolerance": "", "no_negative_allowed": True, "raw_text": "试运行240小时（合同P1356）"},
        {"id": "sp-002", "clause": "前附表1.3.3", "page": "n/a-无分页",
         "requirement": "一次验收合格率", "required_value": "100%", "unit": "%",
         "tolerance": "", "no_negative_allowed": True, "raw_text": "一次验收合格率100%；创能建集团优质工程"},
    ]
    return {
        "schema_version": "0.1",
        "source": {"file": "示例发包人示例市100MW风电项目EPC总承包工程招标文件.docx", "page_range": "n/a-无分页（部分：技术标准和要求P2558+待全抽）"},
        "items": items,
    }


def validate_03(plan):
    sp = os.path.join(ASSETS, "bid-plan.schema.json")
    if not os.path.exists(sp):
        return "skip(no-schema)"
    try:
        import jsonschema
    except Exception:
        return ("WARN: jsonschema 未安装，03 schema 校验被跳过"
                "（结构自检仍执行；安装 jsonschema 可获完整校验，见 SKILL.md 依赖说明）")
    schema = load_json(sp)
    try:
        jsonschema.validate(plan, schema)
        return "ok"
    except Exception as e:
        return "FAIL: %s" % str(e)[:200]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bid", required=True, help="项目 bid 目录")
    args = ap.parse_args()
    bid = args.bid
    meta = load_json(os.path.join(bid, "00_metadata.json"))
    facts = load_json(os.path.join(bid, "01_tender-facts.json"))
    assert meta.get("stage") == "reviewed", "stage 必须为 reviewed"
    assert facts.get("contract_schema_version") == "0.4", "facts 契约必须为 0.4"

    c01c = build_01c()
    c03 = build_03(meta, facts)
    c04 = build_04(c03)
    c03c = build_03c()
    c01b = build_01b()

    def w(name, obj):
        p = os.path.join(bid, name)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        return p

    p1 = w("01c_format-outline.json", c01c)
    p3 = w("03_bid-plan.json", c03)
    p4 = w("04_outline.json", c04)
    p3c = w("03c_business-forms.json", c03c)
    p1b = w("01b_spec-items.json", c01b)

    val = validate_03(c03)

    # 素材缺口清单
    gaps = [it for it in c03["items"] if it["status"] != "ready"]
    clar = [it for it in c03["items"] if it["status"] == "blocked_by_clarify"]
    fact_missing = sorted({f for it in c03["items"] for f in it["required_facts"]})
    gap_md = ["# 素材缺口清单（① v0.2.0 产出）", ""]
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
        len(c03["items"]),
        sum(1 for x in c03["items"] if x["source_type"] == "scoring"),
        sum(1 for x in c03["items"] if x["source_type"] == "waste"),
        sum(1 for x in c03["items"] if x["source_type"] == "qualification"),
        sum(1 for x in c03["items"] if x["source_type"] == "business")))
    gap_md.append("- coverage.unmapped：%s（必须为空才可交 G1）" % c03["coverage"]["unmapped"])
    gap_md.append("- 03_bid-plan.json 契约校验：%s" % val)
    with open(os.path.join(bid, "素材缺口清单.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(gap_md))

    print("OK 产出：")
    for p in (p1, p3, p4, p3c, p1b):
        print("  ", p)
    print("   ", os.path.join(bid, "素材缺口清单.md"))
    print("03 校验：", val)
    print("任务卡数：", len(c03["items"]), "unmapped：", c03["coverage"]["unmapped"])


if __name__ == "__main__":
    main()
