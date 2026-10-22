#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/test_stage2_regression.py — 阶段 2 第一步（③ v0.2.0 正文能力）永久回归

覆盖：
  T2-1 chapter.schema.json 契约自洽：fixtures/05_chapters.sample.md 的 frontmatter
     经 check_facts.parse_frontmatter 解析后过 mini_schema 校验；负例（改
     schema_version／越界 status／缺 g4／缺 g4 子字段）必须被检出；
  T2-2 check_facts 正例：合成 bid（01 评分点基准＋02_facts.yaml＋合法章节）→
     rc=0、错误 0 警告 0（占位段与 [[EV:]] 豁免生效）；
  T2-3 check_facts 负例：未知 [[F:]]（E1）／未知 [[S:]]（E2）／多行无来源段（E3）→
     rc=1 且三类逐条出现；
  T2-4 过渡句降级：单行无数字无标注段 → 警告（W1 过渡句）不致 rc=1；
  T2-5 R1/R2 联动：引用缺 source 事实 → E4；updated_at 超 12 个月 → W1 提示；
  T2-6 字数口径单元：count_text 精确断言（CJK 逐字／拉丁词／标注剔除）；
  T2-7 word_count 集成：MISSING／⚠超偏差／合计／孤儿文件正确；
     04_outline.json 缺失 → rc=2；
  T2-8 ③ v0.2.0 交付物在位：SKILL.md version=0.2.0＋references 5 新件＋scripts 2 件＋
     chapter.schema.json＋README 版本行；IRONLAWS 块与 C9 锚（入口 stage／出口指路）防呆；
  T2-9 ②-B 偏离表逐行（check_compliance --mode B v0.4.0）：正例 5 行全对 rc=0＋
     stage 写回 rechecking；负例跳条/照抄/废标级负偏离/判定空白/出处断链/自造行全检出、
     A-lite 残留【待填】给位置＋缺章未响应；stage 不符 → rc=2 阻断且不写回；
  T2-10 ②-B 跨章一致性（check_consistency v0.4.0）：工期/金额同语义多值 ⚠️、
     名称变体、同值异形（80万＝捌拾万元整）不误报、位置粒度（章节·段落·行号·片段）、
     frontmatter 不混入、stage 不符 rc=2。

用法：python tests/test_stage2_regression.py（退出码 0=全过，1=有失败）
依赖：零三方依赖。
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = ROOT / "skills" / "bid-technical-proposal"
CHECK_FACTS = SKILL_DIR / "scripts" / "check_facts.py"
WORD_COUNT = SKILL_DIR / "scripts" / "word_count.py"
FIXTURES = ROOT / "tests" / "fixtures"

sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(SKILL_DIR / "scripts"))
import mini_schema  # noqa: E402
from check_facts import parse_frontmatter, split_frontmatter  # noqa: E402
from word_count import count_text  # noqa: E402

results = []  # (名称, 通过?, 详情)


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print("%s  %s%s" % ("PASS" if ok else "FAIL", name, ("　— " + detail) if detail and not ok else ""))


def run(args):
    env = dict(os.environ, PYTHONUTF8="1")
    return subprocess.run([sys.executable] + [str(a) for a in args],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", env=env)


# ---------- 合成 bid 工具（示例市真件不入测试，全合成） ----------

FM = '''---
schema_version: "0.1"
chapter_id: {cid}
number: "{num}"
title: {title}
status: draft
word_target: 100
g4:
  confirmed: true
  confirmed_by: "王工"
  confirmed_at: "2026-10-20T10:00:00+08:00"
  route_summary:
    - 路线一（来源：02b_knowledge/kn-001）
    - 路线二（来源：用户确认）
    - 路线三（来源：02_facts/eq-002）
---
'''

TODAY = date.today()
STALE = (TODAY - timedelta(days=400)).isoformat()

SCORING = json.dumps({"scoring": {"items": [{"id": "S-07"}, {"id": "S-12"}]}},
                    ensure_ascii=False)


def facts_yaml(extra=""):
    base = '''qualifications:
  - id: qual-001
    name: 施工总承包壹级
    cert_no: "A-123"
    issuer: 住建部
    valid_to: "2027-06-30"
    source: 证书原件
    updated_at: "%s"
    owner: 张三
    is_decisive: false
equipment:
  - id: eq-002
    name: 混凝土搅拌站
    model: HZS120
    qty: 2
    owned: true
    source: 购置合同
    updated_at: "%s"
    owner: 李四
    is_decisive: false
''' % (TODAY, TODAY)
    return base + extra


STALE_AND_NO_SOURCE = '''performances:
  - id: perf-003
    project: 某风电场EPC
    amount: 12000
    unit: "万元"
    contract_no: "HT-001"
    completed_on: "2024-05-01"
    updated_at: "%s"
    owner: 李四
    is_decisive: false
equipment:
  - id: eq-009
    name: 汽车起重机
    model: QY50
    qty: 1
    owned: false
    source: 租赁合同
    updated_at: "%s"
    owner: 王五
    is_decisive: false
''' % (TODAY, STALE)


def new_bid(facts_text=None):
    """新建合成 bid 目录：05_chapters/ + 02_facts.yaml + 01_tender-facts.json。"""
    bid = tempfile.mkdtemp(prefix="s2_bid_")
    os.makedirs(os.path.join(bid, "05_chapters"))
    write(os.path.join(bid, "02_facts.yaml"), facts_text if facts_text is not None else facts_yaml())
    write(os.path.join(bid, "01_tender-facts.json"), SCORING)
    return bid


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def chapter(bid, cid, body, num="1", title="测试章"):
    """写一个合法 frontmatter 的章节文件。"""
    return write(os.path.join(bid, "05_chapters", cid + ".md"),
                 FM.format(cid=cid, num=num, title=title) + "\n" + body + "\n")


def outline_json(chapters):
    """合成 04_outline.json（镜像 ① outline.schema.json 契约：chapters 节点 10 必填字段）。

    chapters = [(cid, number, title, word_target, order, status)]
    """
    items = [{"id": c, "number": str(n), "title": t, "order": o, "parent": None,
              "depends_on": [], "word_target": w, "scoring_refs": [], "status": s,
              "notes": ""}
             for (c, n, t, w, o, s) in chapters]
    return json.dumps({"schema_version": "0.1", "chapters": items}, ensure_ascii=False)


# ---------- T2-1 chapter.schema.json 契约 ----------

def t2_1():
    text = (FIXTURES / "05_chapters.sample.md").read_text(encoding="utf-8")
    fm, _ = split_frontmatter(text)
    meta = parse_frontmatter(fm)
    schema = json.loads((SKILL_DIR / "assets" / "chapter.schema.json").read_text(encoding="utf-8"))
    errs = mini_schema.validate(meta, schema)
    check("T2-1a fixture frontmatter 过 chapter.schema.json", not errs, "; ".join(errs))
    neg1 = dict(meta, schema_version="9.9")
    neg2 = dict(meta, status="published")
    neg3 = dict(meta); neg3.pop("g4")
    neg4 = json.loads(json.dumps(meta)); del neg4["g4"]["confirmed_by"]
    e = [mini_schema.validate(n, schema) for n in (neg1, neg2, neg3, neg4)]
    check("T2-1b 负例：schema_version 不符须报错", bool(e[0]), "; ".join(e[0]))
    check("T2-1c 负例：status 越界枚举须报错", bool(e[1]), "; ".join(e[1]))
    check("T2-1d 负例：缺 g4 整块须报错", bool(e[2]), "; ".join(e[2]))
    check("T2-1e 负例：g4 缺 confirmed_by 须报错", bool(e[3]), "; ".join(e[3]))


# ---------- T2-2 check_facts 正例 ----------

def t2_2():
    bid = new_bid()
    try:
        chapter(bid, "n-3a2f",
                "本章按评分办法逐点响应，覆盖度 100%。[[S:S-07]]\n\n"
                "机具按混凝土搅拌站 2 座集中配置。[[F:eq-002]]\n\n"
                "【待填：临水临电布置，等待现场踏勘纪要】\n\n"
                "[[EV:ev-001]]")
        r = run([CHECK_FACTS, "--bid", bid])
        ok = r.returncode == 0 and "错误 0、警告 0" in r.stdout
        check("T2-2a 正例 rc=0 且零错误零警告", ok,
              "rc=%s out=%s err=%s" % (r.returncode, r.stdout[-300:], r.stderr[-200:]))
        check("T2-2b 正例无 E 类标记", not re.search(r"\[E[1-4]\]", r.stdout))
    finally:
        shutil.rmtree(bid, ignore_errors=True)


# ---------- T2-3 check_facts 负例 ----------

def t2_3():
    bid = new_bid()
    try:
        chapter(bid, "n-bad1",
                "配置参见机具清单。[[F:eq-999]]\n\n"
                "响应详见评分办法。[[S:S-99]]\n\n"
                "无来源段落第一行含工期 180 天。\n"
                "无来源段落第二行继续无标注。")
        r = run([CHECK_FACTS, "--bid", bid])
        out = r.stdout
        check("T2-3a 负例 rc=1", r.returncode == 1,
              "rc=%s out=%s" % (r.returncode, out[-300:]))
        check("T2-3b E1 未知 [[F:]] 逐条报出", "[E1]" in out and "eq-999" in out)
        check("T2-3c E2 未知 [[S:]] 逐条报出", "[E2]" in out and "S-99" in out)
        check("T2-3d E3 多行无来源段逐条报出", "[E3]" in out)
        check("T2-3e 汇总行错误计数 ≥3", bool(re.search(r"错误 [3-9]", out)))
    finally:
        shutil.rmtree(bid, ignore_errors=True)


# ---------- T2-4 过渡句降级 ----------

def t2_4():
    bid = new_bid()
    try:
        chapter(bid, "n-0d01", "本章为承上启下的过渡说明段。")
        r = run([CHECK_FACTS, "--bid", bid])
        ok = r.returncode == 0 and "[W1] 过渡句" in r.stdout and "警告 1" in r.stdout
        check("T2-4a 单行无数字段降级 W1 不致错", ok,
              "rc=%s out=%s" % (r.returncode, r.stdout[-300:]))
    finally:
        shutil.rmtree(bid, ignore_errors=True)


# ---------- T2-5 R1/R2 联动 ----------

def t2_5():
    bid = new_bid(facts_text=facts_yaml(STALE_AND_NO_SOURCE))
    try:
        chapter(bid, "n-0e01",
                "近年业绩以某风电场项目为代表。[[F:perf-003]]\n\n"
                "吊装采用租赁汽车起重机。[[F:eq-009]]")
        r = run([CHECK_FACTS, "--bid", bid])
        out = r.stdout
        check("T2-5a E4 引用缺 source 事实（R1）rc=1", r.returncode == 1 and "[E4]" in out and "perf-003" in out,
              "rc=%s out=%s" % (r.returncode, out[-400:]))
        check("T2-5b W1 事实超 12 个月未更新（R2）", "[W1]" in out and "eq-009" in out)
        check("T2-5c 仅 1 条 E4（有 source 的 eq-009 不触发）", out.count("[E4]") == 1)
    finally:
        shutil.rmtree(bid, ignore_errors=True)


# ---------- T2-6 字数口径单元 ----------

def t2_6():
    check("T2-6a CJK 逐字＋拉丁串各计 1", count_text("额定电流 1250 A") == 6)
    check("T2-6b [[F:]] 标注不计字", count_text("机具 2 座。[[F:eq-002]]") == 4)
    check("T2-6c 型号连字符合 1 词", count_text("LGJ-240/30 导线") == 3)
    check("T2-6d 全 CJK 按字数", count_text("第三章 投标函") == 6)


# ---------- T2-7 word_count 集成 ----------

def t2_7():
    bid = tempfile.mkdtemp(prefix="s2_wc_")
    try:
        write(os.path.join(bid, "04_outline.json"), outline_json([
            ("n-aaaa", 1, "施工组织设计", 100, 1, "writing"),
            ("n-bbbb", 2, "质量保证体系", 200, 2, "writing"),
            ("n-cccc", 3, "安全文明施工", 100, 3, "writing"),
        ]))
        chapter(bid, "n-aaaa", "施" * 100)
        chapter(bid, "n-cccc", "施" * 150)
        r = run([WORD_COUNT, "--bid", bid])
        out = r.stdout
        ok = (r.returncode == 1 and "MISSING" in out and "+50%" in out
              and "+0%" in out and "未写章 1/3" in out
              and "rc=1" in out and "孤儿文件 0" in out)
        check("T2-7a MISSING/偏差/未写章汇总正确（缺章 rc=1，v0.4.0 口径）", ok,
              "rc=%s out=%s" % (r.returncode, out[-400:]))
        # 孤儿文件：无 outline 节点的章节
        chapter(bid, "n-c0de", "孤儿章")
        r2 = run([WORD_COUNT, "--bid", bid])
        check("T2-7b 孤儿文件被点名", "n-c0de" in r2.stdout)
        # outline 缺失 → rc=2
        bid2 = tempfile.mkdtemp(prefix="s2_wc2_")
        try:
            chapter(bid2, "n-aaaa", "只有章节")
            r3 = run([WORD_COUNT, "--bid", bid2])
            check("T2-7c 缺 04_outline.json → rc=2", r3.returncode == 2)
        finally:
            shutil.rmtree(bid2, ignore_errors=True)
    finally:
        shutil.rmtree(bid, ignore_errors=True)


# ---------- T2-9 ②-B 偏离表逐行（mode B） ----------

CHECK_COMPLIANCE = ROOT / "skills" / "bid-compliance-check" / "scripts" / "check_compliance.py"
CHECK_CONSIST = ROOT / "skills" / "bid-compliance-check" / "scripts" / "check_consistency.py"

SPEC5 = [
    ("sp-001", "通用合同条款9.1.5", "试运行考核周期", "240", "小时", False),
    ("sp-002", "前附表1.3.3", "一次验收合格率", "100%", "%", True),
    ("sp-003", "第五章2.性能指标1）（1）", "全场风电机组可利用率", "≥98%", "%", True),
    ("sp-004", "第五章2.性能指标1）（2）", "弃风弃光电量比例", "≤5%", "%", True),
    ("sp-005", "第五章7.1", "设备完好率", "≥95%", "%", True),
]


def spec_items_json():
    items = [{"id": i, "clause": c, "page": "n/a-无分页", "requirement": r,
              "required_value": v, "unit": u, "tolerance": "",
              "no_negative_allowed": nn, "raw_text": r + "：" + v}
             for (i, c, r, v, u, nn) in SPEC5]
    return json.dumps({"schema_version": "0.1",
                       "source": {"file": "招标文件第五章", "page_range": "n/a-无分页"},
                       "items": items}, ensure_ascii=False)


def new_bid_b(dev_rows=None, extra_cards=(), stale_ch1=None):
    """合成 ②-B bid：①②③ 契约产物 + 08_business/deviation-table.md（dev_rows=表体行）。"""
    bid = tempfile.mkdtemp(prefix="s2_bidB_")
    write(os.path.join(bid, "00_metadata.json"), json.dumps({
        "schema_version": "0.1", "stage": "writing",
        "project": {"name": "示例发包人示例市100MW风电项目EPC总承包工程", "no": "CEZB-2026-001",
                    "purchaser": "示例发包人（示例市）新能源有限公司"},
        "bid_mode": "normal", "deadline": "2026-12-01T10:00+08:00",
    }, ensure_ascii=False))
    write(os.path.join(bid, "01_tender-facts.json"), json.dumps({
        "contract_schema_version": "0.4", "clauses": [],
        "scoring": {"items": []}}, ensure_ascii=False))
    write(os.path.join(bid, "01b_spec-items.json"), spec_items_json())
    write(os.path.join(bid, "01c_format-outline.json"),
          '{"schema_version": "0.1", "typography": {}, "chapters": []}')
    write(os.path.join(bid, "02_facts.md"), "qual-001 资质 有效期至 2027-06-30")
    cards = [
        {"id": "t-0001", "source_type": "waste", "source_ref": "c-0001",
         "chapter_id": "n-1a2b", "response_form": "text", "word_target": 100,
         "required_facts": [], "owner": "", "status": "ready", "notes": ""},
        {"id": "t-0002", "source_type": "scoring", "source_ref": "S-01",
         "chapter_id": "n-2c3d", "response_form": "text", "word_target": 100,
         "required_facts": [], "owner": "", "status": "ready", "notes": ""},
        {"id": "t-0003", "source_type": "qualification", "source_ref": "c-0008",
         "chapter_id": "n-1a2b", "response_form": "scan", "word_target": 100,
         "required_facts": [], "owner": "", "status": "ready", "notes": ""},
    ] + list(extra_cards)
    write(os.path.join(bid, "03_bid-plan.json"), json.dumps(
        {"schema_version": "0.2", "preconditions": {}, "items": cards, "coverage": {}},
        ensure_ascii=False))
    write(os.path.join(bid, "04_outline.json"), outline_json([
        ("n-1a2b", "1", "施工组织设计", 100, 1, "done"),
        ("n-2c3d", "2", "性能指标响应", 100, 2, "done"),
    ]))
    write(os.path.join(bid, "06_compliance", "compliance-report.md"), "（②-A 报告）")
    chapter(bid, "n-1a2b", stale_ch1 if stale_ch1 is not None else "试运行按 240 小时考核组织。",
            num="1", title="施工组织设计")
    chapter(bid, "n-2c3d", "可利用率按全场口径统计。", num="2", title="性能指标响应")
    if dev_rows is not None:
        head = ("| 条目id | 条款号 | 要求项 | 招标要求值 | 单位 | 响应值 | 偏离判定 | 不允许负偏离 | 出处 |\n"
                "|---|---|---|---|---|---|---|---|---|\n")
        write(os.path.join(bid, "08_business", "deviation-table.md"),
              "# 响应偏离表（人工填写）\n\n" + head + "\n".join(dev_rows) + "\n")
    return bid


def dev_row(sp, resp, verdict, src="n-1a2b", req_map=None, no_neg="false"):
    req_map = req_map or {}
    it = next(s for s in SPEC5 if s[0] == sp)
    req = req_map.get(sp, it[3])
    no_neg = "true" if it[5] else "false"
    return ("| %s | %s | %s | %s | %s | %s | %s | %s | %s |"
            % (sp, it[1], it[2], req, it[4], resp, verdict, no_neg, src))


GOOD_ROWS = [
    dev_row("sp-001", "240", "无偏离", "n-1a2b 第2段"),
    dev_row("sp-002", "100%", "无偏离", "n-2c3d 第2段"),
    dev_row("sp-003", "98.5%", "正偏离", "n-2c3d 第2段"),
    dev_row("sp-004", "3%", "正偏离", "n-2c3d 第2段"),
    dev_row("sp-005", "96%", "无偏离", "n-1a2b 第2段"),
]


def t2_9():
    # 正例：5 行全对 + 章节干净 → rc=0，stage 写回 rechecking
    bid = new_bid_b(GOOD_ROWS)
    try:
        r = run([CHECK_COMPLIANCE, "--bid", bid, "--mode", "B"])
        ok = r.returncode == 0 and "已响应 2／响应不足 0／未响应 0／证据类 1" in r.stdout
        check("T2-9a 正例 rc=0 且三态汇总正确", ok,
              "rc=%s out=%s err=%s" % (r.returncode, r.stdout[-300:], r.stderr[-200:]))
        meta = json.loads(open(os.path.join(bid, "00_metadata.json"), encoding="utf-8").read())
        check("T2-9b stage 写回 rechecking", meta.get("stage") == "rechecking",
              "stage=%s" % meta.get("stage"))
        dt = open(os.path.join(bid, "06_compliance", "deviation-table.md"), encoding="utf-8").read()
        check("T2-9c 逐行一致 ✅ 且无错误清单", "✅ 一致" in dt and "## 二、差异清单" in dt and "- ✅ 无" in dt)
    finally:
        shutil.rmtree(bid, ignore_errors=True)

    # 负例：跳条/照抄/废标级负偏离/判定空白/出处断链/自造行 + A-lite 残留与缺章
    rows = [
        dev_row("sp-001", "240", "无偏离", "n-9f9f 第2段"),          # 出处断链
        dev_row("sp-003", "≥98%", "无偏离", "n-2c3d 第2段"),          # 照抄（req 含 ≥）
        dev_row("sp-004", "3%", "", "n-2c3d 第2段"),                 # 判定空白
        dev_row("sp-005", "90%", "负偏离", "n-1a2b 第2段"),          # no_neg=True → 废标级
        "| sp-999 | 第五章9.9 | 自造行 | ≥99% | % | 99% | 无偏离 | false | n-1a2b |",  # 多行
    ]  # sp-002 无行 → 跳条
    bid = new_bid_b(rows,
                    extra_cards=[{"id": "t-0004", "source_type": "scoring", "source_ref": "S-02",
                                  "chapter_id": "n-0bad", "response_form": "text", "word_target": 100,
                                  "required_facts": [], "owner": "", "status": "ready", "notes": ""}],
                    stale_ch1="试运行按 240 小时考核组织。\n\n【待填：临水临电布置】")
    try:
        r = run([CHECK_COMPLIANCE, "--bid", bid, "--mode", "B"])
        out = r.stdout
        check("T2-9d 负例 rc=1", r.returncode == 1, "rc=%s" % r.returncode)
        check("T2-9d2 stdout 汇总（A-lite 三态计数）",
              "已响应 1／响应不足 1／未响应 1／证据类 1" in out, out[-400:])
        dt = open(os.path.join(bid, "06_compliance", "deviation-table.md"), encoding="utf-8").read()
        for kw in ("跳条", "照抄招标要求", "废标级", "偏离判定空白", "出处断链", "多行"):
            check("T2-9e 检出：%s" % kw, kw in dt, dt[-500:])
        check("T2-9f A-lite 未响应（n-0bad 无章节）", "未响应 1" in out
              and "n-0bad" in open(os.path.join(bid, "06_compliance", "compliance-report.md"),
                                   encoding="utf-8").read())
        check("T2-9g A-lite 响应不足（残留【待填】给位置）", "响应不足 1" in out
              and "【待填" in open(os.path.join(bid, "06_compliance", "compliance-report.md"),
                                   encoding="utf-8").read())
        check("T2-9h 废标级负偏离单列（sp-005）", "🔴 sp-005" in dt)
        check("T2-9i 跳条指名 sp-002", "sp-002：跳条" in dt)
    finally:
        shutil.rmtree(bid, ignore_errors=True)

    # 阻断：stage 不符（plan_confirmed）→ rc=2 阻断，不写回 stage、零 ②-B 产物
    bid = new_bid_b(GOOD_ROWS)
    try:
        p = os.path.join(bid, "00_metadata.json")
        m = json.loads(open(p, encoding="utf-8").read())
        m["stage"] = "plan_confirmed"
        json.dump(m, open(p, "w", encoding="utf-8"), ensure_ascii=False)
        r = run([CHECK_COMPLIANCE, "--bid", bid, "--mode", "B"])
        check("T2-9j stage 不符 → rc=2 阻断", r.returncode == 2 and "【执行阻断】" in r.stdout)
        m2 = json.loads(open(p, encoding="utf-8").read())
        check("T2-9k 阻断不写回（stage 仍 plan_confirmed）且零 ②-B 产物",
              m2.get("stage") == "plan_confirmed"
              and not os.path.exists(os.path.join(bid, "06_compliance", "deviation-table.md")))
    finally:
        shutil.rmtree(bid, ignore_errors=True)


# ---------- T2-10 ②-B 跨章一致性（check_consistency v0.4.0） ----------

def t2_10():
    bid = tempfile.mkdtemp(prefix="s2_cc_")
    try:
        write(os.path.join(bid, "00_metadata.json"), json.dumps({
            "schema_version": "0.1", "stage": "writing",
            "project": {"name": "示例发包人示例市100MW风电项目EPC总承包工程", "no": "CEZB-2026-001",
                        "purchaser": "示例发包人（示例市）新能源有限公司"}}, ensure_ascii=False))
        chapter(bid, "n-1a2b",
                "本工程总工期为 180 日历天。\n\n"
                "投标总价为人民币伍仟万元整（¥50,000,000.00）。\n\n"
                "计划 2026 年 12 月 15 日开工。\n\n"
                "招标编号：CEZB-2026-001。",
                num="1", title="施工组织设计")
        chapter(bid, "n-2c3d",
                "总工期按 150 日历天控制。\n\n"
                "投标总价 4800 万元（含税）。\n\n"
                "投标保证金为 80 万元。\n\n"
                "投标保证金金额：捌拾万元整。",
                num="2", title="质量管理")
        chapter(bid, "n-3e4f",
                "本工程名称为示例发包人示例市100MW风电EPC项目总承包（简称本项目）。\n\n"
                "安全生产费用按规计提。",
                num="3", title="安全文明")
        r = run([CHECK_CONSIST, "--bid", bid])
        out = r.stdout
        check("T2-10a 埋 3 处不一致 → rc=1", r.returncode == 1, "rc=%s" % r.returncode)
        md = open(os.path.join(bid, "06_compliance", "consistency-issues.md"), encoding="utf-8").read()
        check("T2-10b 工期 180 vs 150 日历天 检出（同语义多值 ⚠️）",
              "180日历天" in md and "150日历天" in md and "【day·工期】 ⚠️" in md)
        check("T2-10c 金额 4800万 vs 5000万（中文大写+¥）检出",
              "4800万元" in md and "伍仟万元整" in md and "【总价】 ⚠️" in md)
        check("T2-10d 单位名变体检出", "疑似变体" in md and "示例发包人示例市100MW风电EPC项目总承包" in md)
        check("T2-10e 位置粒度＝章节·段落·行号·原文片段",
              "「1 施工组织设计」（n-1a2b） · 第 1 段 · L" in md and "180 日历天" in md)
        check("T2-10e2 日期里的「12 月」不当工期（month 组不报）", "【month·工期】" not in md)
        check("T2-10f 同值异形不误报（80万＝捌拾万元整）",
              "ℹ️ 同值异形" in md and "800000" in md.replace(",", ""))
        check("T2-10f2 保证金组同值 → 不报 ⚠️", "【保证金】 ⚠️" not in md)
        check("T2-10g frontmatter 不混入日期信号", "confirmed_at" not in md)
        # 总价组内 ¥50,000,000.00＝伍仟万元整 → 同值异形信号；4800万≠5000万 → 组 ⚠️ 仍报
        check("T2-10h 总价组同值异形提示且组内 ⚠️ 仍报（4800万≠5000万）",
              md.count("ℹ️ 同值异形") == 2 and "50000000.0" in md.replace(",", ""))
    finally:
        shutil.rmtree(bid, ignore_errors=True)

    # 入口负例：stage 不符（plan_confirmed）→ rc=2
    bid = tempfile.mkdtemp(prefix="s2_cc_")
    try:
        write(os.path.join(bid, "00_metadata.json"), json.dumps({
            "schema_version": "0.1", "stage": "plan_confirmed",
            "project": {"name": "示例发包人示例市100MW风电项目EPC总承包工程", "no": "",
                        "purchaser": "示例发包人（示例市）新能源有限公司"}}, ensure_ascii=False))
        chapter(bid, "n-1a2b", "总工期 180 日历天。", num="1", title="施工组织设计")
        r = run([CHECK_CONSIST, "--bid", bid])
        check("T2-10i check_consistency stage 不符 → rc=2", r.returncode == 2, "rc=%s" % r.returncode)
    finally:
        shutil.rmtree(bid, ignore_errors=True)


# ---------- T2-11 批次 1~4 修复的新行为断言（v0.5.0） ----------

CHECK_BUSINESS = ROOT / "skills" / "bid-compliance-check" / "scripts" / "check_business.py"


def cc_bid(*chapters_bodies):
    """check_consistency 专用最小 bid：00_metadata + 章节文件。"""
    bid = tempfile.mkdtemp(prefix="s2_t11_")
    write(os.path.join(bid, "00_metadata.json"), json.dumps({
        "schema_version": "0.1", "stage": "writing",
        "project": {"name": "示例发包人示例市100MW风电项目EPC总承包工程", "no": "CEZB-2026-001",
                    "purchaser": "示例发包人（示例市）新能源有限公司"}}, ensure_ascii=False))
    for i, body in enumerate(chapters_bodies, 1):
        chapter(bid, "n-%04x" % (0x1a2b + i), body, num=str(i),
                title="第%d章" % i)
    return bid


def t2_11():
    # a/b) C4 关键日期槽：同槽跨章多值 → ⚠️ 抬 rc；同槽同值 → 不报
    bid = cc_bid("投标截止时间为 2026 年 12 月 1 日 10 时。",
                 "投标截止日期 2026年12月8日（以招标文件为准）。")
    try:
        r = run([CHECK_CONSIST, "--bid", bid])
        md = open(os.path.join(bid, "06_compliance", "consistency-issues.md"),
                  encoding="utf-8").read()
        check("T2-11a 截止槽两值 → rc=1 ⚠️", r.returncode == 1
              and "关键日期槽多值" in md and "2026年12月1日" in md and "2026年12月8日" in md,
              "rc=%s" % r.returncode)
    finally:
        shutil.rmtree(bid, ignore_errors=True)
    bid = cc_bid("投标截止时间为 2026-12-01 10 时。",
                 "开标时间即递交截止后另定；投标截止 2026-12-01。")
    try:
        r = run([CHECK_CONSIST, "--bid", bid])
        md = open(os.path.join(bid, "06_compliance", "consistency-issues.md"),
                  encoding="utf-8").read()
        check("T2-11b 截止槽同值 → 不报 ⚠️（rc=0）",
              r.returncode == 0 and "关键日期槽多值" not in md,
              "rc=%s" % r.returncode)
    finally:
        shutil.rmtree(bid, ignore_errors=True)
    # c) C1 混归一：捌拾万元整＝80万（同值异形）＋81万（异值）→ 组 ⚠️ 仍报
    bid = cc_bid("投标保证金为捌拾万元整（小写 80 万元）。",
                 "投标保证金 81 万元，与商务表一致。")
    try:
        r = run([CHECK_CONSIST, "--bid", bid])
        md = open(os.path.join(bid, "06_compliance", "consistency-issues.md"),
                  encoding="utf-8").read()
        check("T2-11c 混归一：异值在场组 ⚠️ 仍报（rc=1）",
              r.returncode == 1 and "【保证金】 ⚠️" in md
              and md.count("ℹ️ 同值异形") == 1, "rc=%s" % r.returncode)
    finally:
        shutil.rmtree(bid, ignore_errors=True)
    # d) C6：draft 章警告不阻断（mode B rc=0；④ 侧硬阻断由 T3-12b 覆盖）
    bid = new_bid_b(GOOD_ROWS)
    try:
        r = run([CHECK_COMPLIANCE, "--bid", bid, "--mode", "B"])
        rep = open(os.path.join(bid, "06_compliance", "compliance-report.md"),
                   encoding="utf-8").read()
        check("T2-11d draft 章警告不阻断", r.returncode == 0
              and "草稿章" in r.stdout and "②-B 阶段不阻断" in rep
              and "④ 导出闸门" in rep, "rc=%s" % r.returncode)
    finally:
        shutil.rmtree(bid, ignore_errors=True)
    # e) C12：mode B 前置缺章（04_outline 节点无章节文件）→ rc=2
    bid = new_bid_b(GOOD_ROWS)
    try:
        p = os.path.join(bid, "04_outline.json")
        oc = json.loads(open(p, encoding="utf-8").read())
        oc["chapters"].append({"id": "n-3e4f", "number": "3", "title": "附表",
                               "order": 3, "parent": None, "depends_on": [],
                               "word_target": 100, "scoring_refs": [],
                               "status": "todo", "notes": ""})
        json.dump(oc, open(p, "w", encoding="utf-8"), ensure_ascii=False)
        r = run([CHECK_COMPLIANCE, "--bid", bid, "--mode", "B"])
        check("T2-11e mode B 缺章 → rc=2 阻断", r.returncode == 2
              and "缺章" in r.stdout and "n-3e4f" in r.stdout, "rc=%s" % r.returncode)
    finally:
        shutil.rmtree(bid, ignore_errors=True)
    # f) C5：qual_timing 三元组（status=整体最坏态 + items 结构化）
    sys.path.insert(0, str(CHECK_COMPLIANCE.parent))
    try:
        import check_compliance as CC
        st, detail, items = CC.qual_timing(
            {"qualifications": [{"id": "qual-001", "valid_to": "2023-06-01"},
                                {"id": "qual-002", "valid_to": "2030-06-30"}]},
            "", date(2026, 12, 1))
        check("T2-11f qual_timing 三元组契约", st == "expired"
              and [x["state"] for x in items] == ["expired", "stated"]
              and {x["fact_id"] for x in items} == {"qual-001", "qual-002"}
              and "废标风险" in detail, "st=%s items=%s" % (st, items))
    finally:
        sys.path.pop(0)
    # g) C8：08_business 行内大小写金额等值核对
    bid = tempfile.mkdtemp(prefix="s2_t11_")
    try:
        write(os.path.join(bid, "00_metadata.json"), json.dumps(
            {"schema_version": "0.1", "stage": "writing"}, ensure_ascii=False))
        write(os.path.join(bid, "08_business", "报价表.md"),
              "投标总价：人民币捌拾万元整（小写：¥800,000.00）。\n"
              "安全生产费用：人民币壹拾万元整（¥100,000.00）。\n")
        r = run([CHECK_BUSINESS, "--bid", bid, "--mode", "B"])
        check("T2-11g 行内大小写等值 → rc=0", r.returncode == 0
              and "不等值 0 对" in r.stdout, "rc=%s out=%s" % (r.returncode, r.stdout[-200:]))
        write(os.path.join(bid, "08_business", "报价表.md"),
              "投标总价：人民币壹仟万元整（小写：¥1,000,000.00）。\n")
        r = run([CHECK_BUSINESS, "--bid", bid, "--mode", "B"])
        check("T2-11g2 行内大小写不等值 → rc=1", r.returncode == 1
              and "行内大小写不等值" in r.stdout, "rc=%s" % r.returncode)
        shutil.rmtree(os.path.join(bid, "08_business"))
        os.makedirs(os.path.join(bid, "08_business"))
        r = run([CHECK_BUSINESS, "--bid", bid, "--mode", "B"])
        check("T2-11h 08_business 空目录 → rc=2", r.returncode == 2, "rc=%s" % r.returncode)
    finally:
        shutil.rmtree(bid, ignore_errors=True)


# ---------- T2-8 ③ v0.2.0 交付物在位 ----------

def t2_8():
    skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    m = re.search(r"^version:\s*(\d+\.\d+\.\d+)\s*$", skill, re.M)
    check("T2-8a SKILL.md version=0.3.1（批次 3–4 修正：lite 新增）", bool(m) and m.group(1) == "0.3.1",
          "version=%s" % (m.group(1) if m else "缺失"))
    refs = ["章节写作五步循环.md", "写作规范.md", "工程类技术标结构参考.md",
            "暗标写作规范.md", "图表与题注规范.md"]
    for f in refs:
        check("T2-8b reference 在位：%s" % f, (SKILL_DIR / "references" / f).exists())
    for f in ["check_facts.py", "word_count.py"]:
        check("T2-8c script 在位：%s" % f, (SKILL_DIR / "scripts" / f).exists())
    check("T2-8d chapter.schema.json 在位", (SKILL_DIR / "assets" / "chapter.schema.json").exists())
    check("T2-8e 铁律块仍成对在位（防呆，主检归 C3/C10）",
          "IRONLAWS:BEGIN" in skill and "IRONLAWS:END" in skill)
    check("T2-8f C9 入口锚（check_confirmed）未损", "`check_confirmed`" in skill)
    check("T2-8g 出口指路（②-B）未损", "bid-compliance-check" in skill)
    readme = (SKILL_DIR / "README.md").read_text(encoding="utf-8")
    check("T2-8h README 同步 v0.3.1", "0.3.1" in readme)


def main():
    for fn in (t2_1, t2_2, t2_3, t2_4, t2_5, t2_6, t2_7, t2_9, t2_10, t2_11, t2_8):
        print("\n== %s ==" % fn.__name__)
        fn()
    failed = [r for r in results if not r[1]]
    print()
    print("阶段 2 回归（T2-1~T2-11）：共 %d 项，通过 %d，失败 %d"
          % (len(results), len(results) - len(failed), len(failed)))
    if failed:
        print("\n失败明细：")
        for name, _, detail in failed:
            print("  FAIL %s　— %s" % (name, detail))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())




