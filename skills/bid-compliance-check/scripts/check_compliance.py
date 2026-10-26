#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
② bid-compliance-check — ②-A 覆盖检查 ＋ ②-B 成稿响应检查
=========================================================
②-A（阶段 1）：读取 ⓪ 事实库(01) / ① 任务卡(03) / 商务表框架(03c) / 格式章(01c) /
事实库(02_facts) / 状态(00_metadata.json)，对「废标项 / 资格项 / 评分点 / 商务表格」
做覆盖闭合检查，输出 06_compliance/ 交付物。
②-B（v0.4.0，阶段 2）：成稿后响应检查——入口校验（stage=writing → 写 rechecking）、
A-lite 任务卡成稿三态（已响应/响应不足/未响应/证据类，残留【待填】给位置）、
B 偏离表逐行（08_business/deviation-table.md × 01b：跳条/多行/重行/照抄/空白判定/
负偏离废标级/出处断链）、F 类 ②-A 结论复核；C 类跨章一致性归 check_consistency.py
（全套件唯一实现），本脚本只提示调用。
只报事实态（已响应 / 响应不足 / 未响应 / 需原件核对），不改写内容，不判定是否废标。

运行要求：Python ≥ 3.12（脚本按 3.12+ 维护；分发到更低版本环境须先升级解释器）。

用法：
  python check_compliance.py --bid <项目/bid目录> [--mode A|B]
  ②-B 退出码：0＝无错误项；1＝存在错误/废标级负偏离/阻断（G5 前须闭环）；
  2＝前置缺失（阻断输出格式，零产物）。
"""
import argparse
import datetime as _dt
import json
import os
import re
import sys
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


# 第五章「发包人要求」节号→节名（招标文件结构，非逐批计数；新增节才需补表）
CH5_SECTION_NAMES = {
    1: "总则", 2: "性能指标", 3: "勘察设计", 4: "施工安装",
    5: "风电场调试、试运行和验收", 6: "施工工期", 7: "施工质量",
    8: "竣工试验与验收", 9: "工程管理",
}


def summarize_01b(spec_items_path):
    """从 01b_spec-items.json **动态派生**第五章覆盖口径（根治硬编码计数漂移：
    ① 每全量一批，历史口令行必漂移一次）。返回 (总条数, 口径摘要字符串)。
    口径：clause 以「第五章<节号>」开头即计入该节；有条目=已全量，无=挂起。"""
    try:
        data = load(spec_items_path)
    except Exception:
        return None, None
    items = data.get("items", [])
    per_section = Counter()
    for it in items:
        m = re.match(r"第五章(\d+)", str(it.get("clause", "")))
        if m:
            per_section[int(m.group(1))] += 1
    done = sorted(s for s in per_section if per_section[s] > 0)
    todo = sorted(s for s in CH5_SECTION_NAMES if s not in per_section)
    n_ch5 = sum(per_section.values())
    done_s = "＋".join(f"{CH5_SECTION_NAMES[s]} {per_section[s]} 行" for s in done)
    todo_s = "/".join(f"{s}.{CH5_SECTION_NAMES[s]}" for s in todo) or "无"
    summary = (f"第五章已全量 {len(done)} 节（{done_s}；共 {n_ch5} 行），"
               f"挂起 {todo_s}——不得冒充第五章全覆盖")
    return len(items), summary


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

    返回 (整体最坏态, 人读明细串, items 结构化列表)；items 供 ④ gate 联动阻断
    （f_qual_timing.items[].state == "expired" 契约，与整体 status 双保险）。
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
                return ("fact_missing",
                        "metadata.deadline 缺失或不可解析，无法作为时效基准；须人工录入截止日后重跑",
                        [{"fact_id": cid, "valid_to": str(vt), "state": "unknown"} for cid, vt in certs])
            worst = "stated"
            details = []
            items = []
            for cid, vt in certs:
                v = vt if isinstance(vt, _dt.date) else norm_date(str(vt))
                if v is None:
                    details.append(f"{cid} valid_to={vt} 不可解析")
                    items.append({"fact_id": str(cid), "valid_to": str(vt), "state": "unparseable"})
                    continue
                if v < deadline_date:
                    worst = "expired"
                    details.append(f"{cid} valid_to={vt} 早于截止日({deadline_date})→废标风险")
                    items.append({"fact_id": str(cid), "valid_to": str(vt), "state": "expired"})
                elif v <= deadline_date + _dt.timedelta(days=180):
                    if worst != "expired":
                        worst = "expiring_soon"
                    details.append(f"{cid} valid_to={vt} 落入换证窗口(截止后180天内)")
                    items.append({"fact_id": str(cid), "valid_to": str(vt), "state": "expiring_soon"})
                else:
                    details.append(f"{cid} valid_to={vt} 有效")
                    items.append({"fact_id": str(cid), "valid_to": str(vt), "state": "stated"})
            return worst, ("；".join(details) if details else "未解析到有效日期"), items
    # 退化：扫描 md 正则（兜底）
    certs_md = CERT_VALID_RE.findall(facts_text)
    if not certs_md:
        if FACT_ID_RE.search(facts_text):
            return ("fact_missing",
                    "事实库含事实ID但缺结构化证书有效期字段，时效不可判；须回①补录后重跑", [])
        return ("fact_missing",
                "事实库(02_facts.yaml/.json)未含结构化事实条目（无 qual/pers 有效期），时效不可判；属资料缺口，须回①补录", [])
    if deadline_date is None:
        return ("fact_missing",
                "metadata.deadline 缺失或不可解析，无法作为时效基准；须人工录入截止日后重跑",
                [{"fact_id": "md-scan", "valid_to": str(cv), "state": "unknown"} for cv in certs_md])
    worst = "stated"
    details = []
    items = []
    for cv in certs_md:
        v = norm_date(cv)
        if v is None:
            continue
        if v < deadline_date:
            worst = "expired"
            details.append(f"{cv} 早于截止日({deadline_date})")
            items.append({"fact_id": "md-scan", "valid_to": str(cv), "state": "expired"})
        elif v <= deadline_date + _dt.timedelta(days=180):
            if worst != "expired":
                worst = "expiring_soon"
            details.append(f"{cv} 落入换证窗口(截止后180天内)")
            items.append({"fact_id": "md-scan", "valid_to": str(cv), "state": "expiring_soon"})
        else:
            details.append(f"{cv} 有效")
            items.append({"fact_id": "md-scan", "valid_to": str(cv), "state": "stated"})
    return worst, ("；".join(details) if details else "未解析到有效日期"), items


# ================= ②-B 成稿响应检查（v0.4.0，阶段 2 实装） =================
# 依据：计划书 §4.3（A/B/F 三类的 ②-B 列）、§11.2 验收 #5（偏离表逐条无合并/跳条）、
# 交接约定 §二（②-B 前置＝②-A 全部＋05_chapters）§五（rechecking 写回）、
# references/响应偏离表模板.md（人工填写契约：08_business/deviation-table.md）。

PLACEHOLDER_RE = re.compile(r"【(?:待填|待确认)[^】]*】")
CHAPTER_FILE_RE = re.compile(r"^(n-[0-9a-f]{4})(?:_.*)?\.md$")
SP_ID_RE = re.compile(r"^sp-\d{3,}$")
# 含限定符的要求值——照抄此类值无法证明真实匹配（F3：禁照抄原文）
QUALIFIER_RE = re.compile(r"[≥≤<>]|不低于|不高于|不超过|不少于|至少|最多|以上|以下")
VALID_VERDICTS = {"正偏离", "负偏离", "无偏离", "无"}
VAGUE_POS_RE = re.compile(r"^(?:优于(?:招标)?要求|满足并优于|优于)$")


def _body_text(text):
    """剥离 frontmatter（③ 章节契约）；无 frontmatter 原样返回。"""
    m = re.match(r"^---\s*\n.*?\n---\s*\n?", text, re.S)
    return text[m.end():] if m else text


def _fm_status(text):
    """frontmatter status 行（chapter.schema：draft=步4草稿 / final=步5复核通过）。

    无 frontmatter 或无 status 行 → ""（③ 契约要求必填；缺即事实态，按 draft 报）。
    """
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?", text, re.S)
    if not m:
        return ""
    for ln in m.group(1).splitlines():
        mm = re.match(r"^status:\s*['\"]?(\w+)['\"]?\s*$", ln.strip())
        if mm:
            return mm.group(1)
    return ""


def _norm_cell(s):
    """表格单元格规范化：去空白与引号，供照抄/要求值比对。"""
    return re.sub(r"\s+", "", (s or "").strip().strip('"').strip("'"))


def load_chapters_b(bid):
    """05_chapters/*.md → {chapter_id: {"fn":…, "residuals": [(段号, 行号, 片段)]}}。

    residuals＝正文中残留的【待填/待确认】（③ 契约要求 final 前清零；
    ②-B 复查：残留即响应不足证据，给位置）。
    """
    out = {}
    d = os.path.join(bid, "05_chapters")
    for fn in sorted(os.listdir(d)):
        m = CHAPTER_FILE_RE.match(fn)
        if not m:
            continue
        with open(os.path.join(d, fn), encoding="utf-8") as f:
            text = f.read()
        body = _body_text(text).splitlines()
        residuals, para, in_blk = [], 0, False
        for i, ln in enumerate(body):
            if ln.strip():
                if not in_blk:
                    para += 1
                    in_blk = True
                for pm in PLACEHOLDER_RE.finditer(ln):
                    residuals.append((para, i + 1, pm.group(0)))
            else:
                in_blk = False
        out[m.group(1)] = {"fn": fn, "residuals": residuals, "status": _fm_status(text)}
    return out


def parse_deviation_table(path):
    """解析人工填写的偏离表（references/响应偏离表模板.md 契约）。

    返回 (rows, problems)：rows＝数据行字典列表；problems＝表头级问题（缺列/
    无表头，阻断逐行检查）。列名定位而非列序，容列序调整。
    """
    rows, problems, header = [], [], None
    with open(path, encoding="utf-8") as f:
        lines = f.read().splitlines()
    for ln in lines:
        s = ln.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if header is None:
            if "条目id" in cells:
                header = cells
                for c in ("条目id", "招标要求值", "响应值", "偏离判定", "出处"):
                    if c not in cells:
                        problems.append(f"表头缺列「{c}」（按 references/响应偏离表模板.md 补齐）")
            continue
        if all(re.fullmatch(r":?-{3,}:?", c) for c in cells if c):
            continue  # 分隔行
        rows.append(cells)
    if header is None:
        problems.append("未找到含「条目id」的表头行（按 references/响应偏离表模板.md 重排）")
        return [], problems
    idx = {name: i for i, name in enumerate(header)}

    def col(cells, name):
        i = idx.get(name)
        return cells[i] if i is not None and i < len(cells) else ""

    out = [{"id": col(c, "条目id"), "clause": col(c, "条款号"), "requirement": col(c, "要求项"),
            "required": col(c, "招标要求值"), "unit": col(c, "单位"), "response": col(c, "响应值"),
            "verdict": col(c, "偏离判定"), "no_neg_col": col(c, "不允许负偏离"),
            "source": col(c, "出处")} for c in rows]
    return out, problems


def mode_b(bid):
    """②-B 成稿响应检查（v0.4.0）：入口校验 → stage=rechecking →
    A-lite 成稿三态 ＋ B 偏离表逐行 ＋ F 处置提示 → G5 指引（不自动写 recheck_confirmed）。
    """
    meta_p = os.path.join(bid, "00_metadata.json")
    if not os.path.exists(meta_p):
        print("【执行阻断】bid-compliance-check（②-B）未执行")
        print("原因：缺 00_metadata.json（流水线状态载体，⓪ 出口产出）")
        print("处置：请先执行 ⓪ tender-document-review，产出 01_tender-facts.json 与 00_metadata.json")
        return 2
    with open(meta_p, encoding="utf-8") as f:
        meta = json.load(f)
    stage = meta.get("stage")
    if stage not in ("writing", "rechecking"):
        print("【执行阻断】bid-compliance-check（②-B）未执行")
        print(f"原因：stage={stage}，②-B 要求 writing（rechecking 为 ②-B 重跑态）")
        print("处置：请先完成 ③ 正文成稿（stage=writing）后重试本技能")
        return 2

    prereq = ["01_tender-facts.json", "01b_spec-items.json", "01c_format-outline.json",
              "03_bid-plan.json", "04_outline.json",
              os.path.join("06_compliance", "compliance-report.md")]
    missing = [p for p in prereq if not os.path.exists(os.path.join(bid, p))]
    if not any(os.path.exists(os.path.join(bid, f))
               for f in ("02_facts.md", "02_facts.yaml", "02_facts.json")):
        missing.append("02_facts.(md|yaml|json)")
    ch_dir = os.path.join(bid, "05_chapters")
    if not (os.path.isdir(ch_dir)
            and any(CHAPTER_FILE_RE.match(f) for f in os.listdir(ch_dir))):
        missing.append("05_chapters/*.md（n-xxxx 命名成稿）")
    if missing:
        print("【执行阻断】bid-compliance-check（②-B）未执行")
        print(f"原因：前置产物缺件；当前 stage={stage}（要求 writing）")
        print("缺少产物：")
        for p in missing:
            print("  -", p)
        print("处置：缺 ②-A 产物先跑 --mode A；缺 05_chapters 先完成 ③ bid-technical-proposal 正文")
        return 2

    # ---------- 缺章阻断（04_outline 节点 vs 05_chapters 文件，写作未完成不查成稿）----------
    outline_p = os.path.join(bid, "04_outline.json")
    try:
        with open(outline_p, encoding="utf-8") as f:
            outline_chapters = json.load(f).get("chapters", [])
    except (OSError, json.JSONDecodeError) as e:
        print("【执行阻断】bid-compliance-check（②-B）未执行")
        print(f"原因：04_outline.json 不可解析：{e}")
        return 2
    have = set(load_chapters_b(bid))
    miss_ch = [str(c.get("id")) for c in outline_chapters if str(c.get("id")) not in have]
    if miss_ch:
        print("【执行阻断】bid-compliance-check（②-B）未执行")
        print(f"原因：05_chapters 缺章 {len(miss_ch)}/{len(outline_chapters)}（04_outline 有节点而无对应章节文件，写作未完成）")
        for cid in miss_ch[:10]:
            print("  -", cid)
        if len(miss_ch) > 10:
            print(f"  …（共 {len(miss_ch)} 章）")
        print("处置：回 ③ 完成全部章节后再跑 ②-B（可用 ③ word_count.py 核对 MISSING）")
        return 2

    # ---------- stage → rechecking（交接约定 §五：五项必写）----------
    skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 技能根（scripts 上一级）
    with open(os.path.join(skill_dir, "SKILL.md"), encoding="utf-8") as f:
        vself = (re.search(r"^version:\s*(\d+\.\d+\.\d+)\s*$", f.read(), re.M) or [None, "?"])[1]
    meta["stage"] = "rechecking"
    meta.setdefault("skill_versions", {})["bid-compliance-check"] = vself
    meta["updated_at"] = _dt.datetime.now().astimezone().replace(microsecond=0).isoformat()
    with open(meta_p, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)

    spec = load(os.path.join(bid, "01b_spec-items.json"))
    items = {it["id"]: it for it in spec.get("items", [])}
    plan = load(os.path.join(bid, "03_bid-plan.json"))

    # ---------- A-lite：任务卡成稿三态 ----------
    chapters = load_chapters_b(bid)
    tri = []
    for card in plan.get("items", []):
        cid = card.get("chapter_id", "")
        ch = chapters.get(cid)
        if card.get("response_form") == "scan":
            tri.append((card["id"], "证据类", cid, "扫描件响应，正文不适用（④ 装配时核对）"))
        elif ch is None:
            tri.append((card["id"], "未响应", cid, "章节文件缺失（05_chapters/ 无此章节）"))
        elif ch["residuals"]:
            locs = "；".join(f"第{p}段L{l}:{frag}" for p, l, frag in ch["residuals"][:3])
            more = "" if len(ch["residuals"]) <= 3 else f"（共 {len(ch['residuals'])} 处）"
            tri.append((card["id"], "响应不足", cid, f"残留【待填/待确认】{more}：{locs}"))
        else:
            tri.append((card["id"], "已响应", cid, ""))
    n_ok = sum(1 for t in tri if t[1] == "已响应")
    n_ins = sum(1 for t in tri if t[1] == "响应不足")
    n_no = sum(1 for t in tri if t[1] == "未响应")
    n_ev = sum(1 for t in tri if t[1] == "证据类")
    # draft 章警告（③ 契约：final=步 5 背对背复核通过；②-B 阶段允许 draft，④ 导出硬阻断）
    drafts = [cid for cid, ch in chapters.items() if ch["status"] != "final"]

    # ---------- F 类：②-A 结论复核（不重判，列处置义务）----------
    structured = _load_structured_facts(bid)
    facts_text = ""
    p02 = os.path.join(bid, "02_facts.md")
    if os.path.exists(p02):
        with open(p02, encoding="utf-8") as f:
            facts_text = f.read()
    deadline_date = parse_deadline(meta.get("deadline"))
    f_status, f_detail, _f_items = qual_timing(structured, facts_text, deadline_date)

    # ---------- B 类：偏离表逐行（计划书 §11.2 验收 #5）----------
    dev_p = os.path.join(bid, "08_business", "deviation-table.md")
    b_blocked, rows, errs, warns, fatal_neg = False, [], [], [], []
    if not os.path.exists(dev_p):
        b_blocked = True
    else:
        rows, problems = parse_deviation_table(dev_p)
        errs.extend(("-", "-", p) for p in problems)
        seen = defaultdict(int)
        for r in rows:
            seen[r["id"]] += 1
        for r in rows:
            sp = r["id"]
            if not SP_ID_RE.match(sp):
                errs.append((sp, sp, f"非法条目id「{sp}」（须 01b 主键 sp-xxx）"))
                continue
            if sp not in items:
                errs.append((sp, sp, "多行（01b 无此条目，疑自造/错抄）"))
                continue
            if seen[sp] > 1:
                errs.append((sp, sp, f"重行（出现 {seen[sp]} 次，疑合并/复制）"))
                continue
            it = items[sp]
            req = _norm_cell(it.get("required_value", ""))
            resp, verdict = _norm_cell(r["response"]), _norm_cell(r["verdict"])
            if r["required"] and _norm_cell(r["required"]) != req:
                errs.append((sp, sp, "招标要求值抄录不一致（疑错行，对照 01b）"))
            if not resp:
                errs.append((sp, sp, "响应值空白（按未响应：无偏离也须显式填写）"))
            elif req and resp == req and QUALIFIER_RE.search(req):
                errs.append((sp, sp, f"照抄招标要求「{req}」（无法证明真实匹配，按未响应——F3）"))
            if not verdict:
                errs.append((sp, sp, "偏离判定空白（按未响应）"))
            elif verdict not in VALID_VERDICTS:
                errs.append((sp, sp, f"非法判定值「{verdict}」（限 正偏离/负偏离/无偏离/无）"))
            if verdict == "负偏离":
                if it.get("no_negative_allowed"):
                    fatal_neg.append((sp, "不允许负偏离条款出现负偏离（01b 标记，废标级事实态）"))
                else:
                    warns.append((sp, "负偏离（01b 未标不允许；事实态报出，处置由人定夺）"))
            if verdict == "正偏离" and VAGUE_POS_RE.match((r["response"] or "").strip()):
                errs.append((sp, sp, "正偏离不具体（须给具体数值/内容，不得只写「优于要求」）"))
            src = (r["source"] or "").strip()
            if not src:
                errs.append((sp, sp, "出处空白（铁律 7：每段可回溯）"))
            else:
                m2 = re.search(r"n-[0-9a-f]{4}", src)
                if m2 and m2.group(0) not in chapters:
                    errs.append((sp, sp, f"出处断链（{m2.group(0)} 在 05_chapters/ 无对应文件）"))
        for sp in items:
            if seen.get(sp, 0) == 0:
                errs.append((sp, sp, "跳条（01b 有此条而偏离表无行）"))
    n_skip = sum(1 for _, _, d in errs if d.startswith("跳条"))
    n_extra = sum(1 for _, _, d in errs if d.startswith("多行"))
    n_dup = sum(1 for _, _, d in errs if d.startswith("重行"))

    # ---------- 报告落盘 ----------
    out_dir = os.path.join(bid, "06_compliance")
    os.makedirs(out_dir, exist_ok=True)
    md = ["# 响应偏离表逐条判定（②-B · B 类，v0.4.0）", ""]
    md.append(f"> 输入：08_business/deviation-table.md（人工填写）× 01b_spec-items.json（{len(items)} 条）。")
    md.append("> 口径：只报事实态，不替投标人选定处置；照抄招标要求＝无法证明真实匹配，按未响应（F3）。")
    md.append("")
    if b_blocked:
        md.append("## B 类阻断（blocked_by_contract）")
        md.append("- 08_business/deviation-table.md 缺失：请按 references/响应偏离表模板.md 人工填写后重跑。")
    else:
        md.append("## 一、逐行一致性")
        ok_rows = (len(rows) - n_extra - n_dup) if len(rows) >= (n_extra + n_dup) else 0
        md.append(f"- 偏离表行数 {len(rows)} vs 01b 条目 {len(items)}："
                  f"{'✅ 一致' if len(rows) == len(items) else '❌ 不一致'}；可对行 {ok_rows}/{len(items)}")
        md.append(f"- 跳条 {n_skip}、多行 {n_extra}、重行 {n_dup}（合并单元格拆行/跳条见 模板·填法铁则 4）。")
        md.append("")
        md.append("## 二、差异清单（错误级，全部闭环后方可过 G5）")
        if errs:
            for _, sp, d in errs:
                md.append(f"- ❌ {sp}：{d}")
        else:
            md.append("- ✅ 无")
        md.append("")
        md.append("## 三、废标级负偏离单列（事实态，处置由人定夺）")
        if fatal_neg:
            for sp, d in fatal_neg:
                md.append(f"- 🔴 {sp}：{d}")
        else:
            md.append("- ✅ 无")
        if warns:
            md.append("")
            md.append("## 四、警告")
            for sp, d in warns:
                md.append(f"- ⚠️ {sp}：{d}")
    with open(os.path.join(out_dir, "deviation-table.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md))

    # ---------- 暗标终检（v0.5.2 机检化；判据与 ④ verify_docx 一致）----------
    # 对象＝05_chapters/*.md（此时尚未导出，早于 ④ 的 docx/pdf 层检查发现标识串）。
    # 铁律 3：暗标项目全文不得出现投标人名称、标识、人员姓名及其他可识别信息。
    blind_errs, blind_notes = [], []
    try:
        _fmt = load(os.path.join(bid, "01c_format-outline.json"))
    except (OSError, json.JSONDecodeError) as e:
        _fmt = {}
        blind_notes.append(f"01c_format-outline.json 不可解析，暗标词条无法读取：{e}")
    identities = [s for s in (((_fmt.get("typography") or {}).get("identity_ban")) or [])
                  if str(s).strip()]
    if meta.get("bid_mode") == "blind":
        if not identities:
            blind_notes.append("identity_ban 为空（01c.typography）：未做暗标词匹配，"
                               "请先在 01c 补录投标人标识串（公司名/人名/商标等）后重跑")
        else:
            _ch_dir = os.path.join(bid, "05_chapters")
            for fn in sorted(os.listdir(_ch_dir)) if os.path.isdir(_ch_dir) else []:
                if not fn.endswith(".md"):
                    continue
                try:
                    with open(os.path.join(_ch_dir, fn), encoding="utf-8") as fh:
                        raw = fh.read()
                except OSError:
                    continue
                body = re.sub(r"^---\n.*?\n---\n", "", raw, flags=re.S)  # 去 YAML frontmatter
                for ident in identities:
                    for ln, line in enumerate(body.splitlines(), 1):
                        if ident in line:
                            blind_errs.append(
                                f"暗标标识命中[正文] {fn}·第{ln}行：{ident}"
                                f"（内容修改归 ③；位图型扫描件无文本层，另须人工抽检）")

    # compliance-report.md 追加 ②-B 节（保留 ②-A 记录，追加不覆盖）
    with open(os.path.join(out_dir, "compliance-report.md"), "a", encoding="utf-8") as f:
        f.write("\n\n## 十一、②-B 成稿响应复查（v0.4.0，stage=rechecking）\n\n")
        f.write(f"- A-lite 三态：已响应 {n_ok}／响应不足 {n_ins}／未响应 {n_no}／证据类 {n_ev}"
                f"（任务卡 {len(tri)} 张）\n")
        if drafts:
            f.write(f"- ⚠️ 草稿章 {len(drafts)}/{len(chapters)}（status≠final，未过 ③ 步 5 背对背复核）："
                    + "、".join(drafts[:8]) + ("…" if len(drafts) > 8 else "") + "\n")
            f.write("  （②-B 阶段不阻断；④ 导出闸门对 status≠final 硬阻断——导出前须完成全部复核）\n")
        for cid_, st_, ch_, note_ in tri:
            if st_ != "已响应":
                f.write(f"  - {st_}：{cid_}（{ch_}）{note_}\n")
        f.write(f"- B 偏离表：{'阻断（08_business/deviation-table.md 缺失）' if b_blocked else f'错误 {len(errs)} 项、废标级负偏离 {len(fatal_neg)} 项（明细见 deviation-table.md）'}\n")
        f.write(f"- F 类（②-A 结论复核，不重判）：{f_status}——{f_detail[:120]}\n")
        if meta.get("bid_mode") == "blind":
            f.write(f"- 暗标终检（机检：05_chapters 全文 vs identity_ban {len(identities)} 串）："
                    f"{'❌ 命中 ' + str(len(blind_errs)) + ' 处' if blind_errs else '✅ 无命中'}\n")
            for e in blind_errs[:20]:
                f.write(f"  - ❌ {e}\n")
            if len(blind_errs) > 20:
                f.write(f"  - ……（共 {len(blind_errs)} 处）\n")
            for n in blind_notes:
                f.write(f"  - ⚠️ {n}\n")

    print(f"②-B 检查完成 → {out_dir}")
    print(f"  A-lite：已响应 {n_ok}／响应不足 {n_ins}／未响应 {n_no}／证据类 {n_ev}（{len(tri)} 张卡）")
    if drafts:
        print(f"  ⚠️ 草稿章 {len(drafts)}/{len(chapters)}（status≠final，未过 ③ 步 5 复核；②-B 不阻断，④ 导出硬阻断）")
    print(f"  B 偏离表：{'阻断（08_business 缺 filled 表）' if b_blocked else f'错误 {len(errs)}、废标级负偏离 {len(fatal_neg)}'}")
    print(f"  F 类：{f_status}｜G5 前须逐条处置 ②-A 遗留 expired 项")
    if meta.get("bid_mode") == "blind":
        if blind_errs:
            print(f"  暗标终检：❌ 命中 {len(blind_errs)} 处（05_chapters 正文含 identity_ban 标识串）")
            for e in blind_errs[:5]:
                print("    -", e)
            if len(blind_errs) > 5:
                print(f"    ……（共 {len(blind_errs)} 处，完整清单见 compliance-report.md / deviation-table.md）")
        else:
            print(f"  暗标终检：✅ 无命中（{len(identities)} 串已扫 05_chapters 全文）")
        for n in blind_notes:
            print("   ⚠️", n)
    print("  C 类一致性：另跑 python scripts/check_consistency.py --bid <bid>（全套件唯一实现）")
    print("下一步：G5 成稿终检（人工：背对背复核差异清单闭环、跨章不一致、暗标终检、独立性自查）")
    print("关卡：G5（人工确认后改写 stage → recheck_confirmed，再调用 bid-docx-export（④））")
    print("回退：重大未响应/跨章不一致 → stage 改回 writing 交 ③ 改正文（≤2 轮，耗尽置 exhausted）")
    rc = 0 if (not errs and not fatal_neg and not b_blocked and n_no == 0
               and n_ins == 0 and not blind_errs) else 1
    return rc


def gate_a(bid):
    """②-A 入口闸门（形态对齐 ④ `_common.gate()` / 本文件 `mode_b`）：缺一即拒，rc=2，零产物。

    依据 `references/流水线交接约定.md` L92：stage=plan_confirmed（checking 为②-A 重跑态）；
    前置＝`01` / `01b` / `01c` / `03_bid-plan.json` / `04_outline.json` / `02_facts`。
    """
    banner = "【执行阻断】bid-compliance-check（②-A）未执行"
    stages = ("plan_confirmed", "checking")
    hint = {
        "reviewed": "尚未生成任务卡；请先执行 ① bid-response-plan 产出 01b/01c/03/04 后重试",
        "facts_confirmed": "① 已过 G2、尚未出任务卡；请先执行 ① bid-response-plan 后重试",
        "planning": "① 正在生成中；请待其产出 01b/01c/03/04 并过 G1 后重试",
        "check_confirmed": "已过 G3，下一步 ③ bid-technical-proposal 写正文；②-A 已完成无需重跑",
        "route_confirmed": "③ bid-technical-proposal 写作中（已过首章 G4）",
        "writing": "已进入成稿阶段；成稿检查请用 ②-B（`--mode B`）",
        "rechecking": "②-B 执行中；成稿检查请用 ②-B（`--mode B`）",
        "recheck_confirmed": "已过 G5，下一步 ④ bid-docx-export 导出",
        "exported": "④ 已导出完成",
    }

    pmeta = os.path.join(bid, "00_metadata.json")
    if not os.path.exists(pmeta):
        return 2, [banner,
                   "原因：缺 00_metadata.json（流水线状态载体，⓪ 出口产出）",
                   "处置：请先执行 ⓪ tender-document-review，再依次执行 ① bid-response-plan"]
    try:
        with open(pmeta, encoding="utf-8") as f:
            meta = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return 2, [banner,
                   f"原因：00_metadata.json 不可解析：{e}",
                   "处置：重跑 ⓪ tender-document-review 修复该产物后重试"]

    stage = meta.get("stage")
    if stage not in stages:
        msg = hint.get(stage, f"未知 stage：{stage!r}（请核对 references/流水线交接约定.md 的 stage 表）")
        return 2, [banner,
                   f"原因：stage={stage!r}，②-A 要求 plan_confirmed（checking 为 ②-A 重跑态）",
                   f"处置：{msg}"]

    missing = [p for p in ("01_tender-facts.json", "01b_spec-items.json",
                           "01c_format-outline.json", "03_bid-plan.json",
                           "04_outline.json")
               if not os.path.exists(os.path.join(bid, p))]
    if missing:
        return 2, [banner,
                   f"原因：前置产物缺件；当前 stage={stage}",
                   "缺少产物："] + ["  - " + p for p in missing] + [
                   "处置：缺 01b/01c/03/04 先跑 ① bid-response-plan（python skills/bid-response-plan/scripts/build_bid_plan.py --bid <项目>/bid）；"
                   "缺 01 先跑 ⓪ tender-document-review"]

    for p in ("01_tender-facts.json", "01b_spec-items.json", "01c_format-outline.json",
              "03_bid-plan.json", "04_outline.json"):
        try:
            json.load(open(os.path.join(bid, p), encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            return 2, [banner,
                       f"原因：{p} 不可解析：{e}",
                       "处置：重跑产出该文件的技能修复后重试"]

    # 02_facts：交接约定「可缺，缺则 blocked_by_facts 并显式告警」——⚠️ 不阻断
    warns = []
    if not any(os.path.exists(os.path.join(bid, f))
               for f in ("02_facts.md", "02_facts.yaml", "02_facts.json")):
        warns.append("⚠️ 缺 02_facts.(md|yaml|json)——涉及事实库的任务卡将置 blocked_by_facts"
                     "（交接约定：可缺但须显式告警，不得按「默认就绪」处理）")
    return 0, warns


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bid", required=True, help="项目 bid 目录")
    ap.add_argument("--mode", choices=["A", "B"], default="A")
    args = ap.parse_args()
    bid = args.bid

    if args.mode == "B":
        return mode_b(bid)

    rc, msgs = gate_a(bid)
    for m in msgs:
        print(m)
    if rc != 0:
        return rc  # 缺件：阻断，零产物（此时不得创建 06_compliance/）

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
    f_status, f_detail, f_items = qual_timing(structured_facts, facts_text, deadline_date)

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
        "f_qual_timing": {"status": f_status, "items": f_items,
                          "required_facts": required_facts,
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
                n01b, cov = summarize_01b(spec_items)
                f.write(f"- 偏离表行 vs 01b 技术规范条目：01b 现有 {n01b} 条（{cov}），逐行一致性以 01b 全量后重跑为准。\n")
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
    sys.exit(main())
