#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/test_stage1_regression.py — v0.16 阶段 1 验收 P0 两项修复的永久回归

覆盖（对应验收记录第五节优先级表 P0×2 + P1）：
  R1 ⓪ D5 加权闭合口径：tender-facts.schema.json 三新字段
     （scoring.total_stated / scoring.weight_basis / scoring.items[].weight）
     + emit_facts.py 两种口径（直接相加 / 加权闭合）验算与回退逻辑；
  R2 ① 01c 章节树保真：FORMAT_CHAPTERS 与原文格式章逐字一致（编号不重排、
     括号说明不删），经 build_bid_plan.py 端到端生成后由
     verify_format_chapters.py 机检（含负例：重排＋删括号必须被检出）；
  R2c D1 章节树真实派生全链（Todo 10 第 3 批）：⓪ emit_headings.py 序列化
     _headings_*.json（契约/条数守恒/溯源三件套）→ ① build_bid_plan 真实
     派生 01c＋03c 商务表锚定（BUSINESS_FORMS 24 表名逐字）→
     verify_format_chapters B 态派生重放（含负例：手改 01c 编号必须被检出）；
  R4 ① 01b 引文逐行机检（check_01b_rawtext.check_items 逻辑回归，合成数据：
     照录通过；改数值/无省略号截断/锚点不存在必须被检出）；
     R4-6 补 load_units 单元提取回归（P 行正文含制表符拼全部字段；
     T 行末列为空时非末列数据不丢——示例市 T39 图纸资料分配表缺口修复固化）；
     R4-7 补 T 行单元格边界语义（引文可自单元格边界起并跨单元格、中英标点
     等价；单元格内非边界截断仍检出——示例市 T1R10 回归与归一化遗漏两缺陷固化）；
  R5 ② 01b 覆盖口径动态派生（check_compliance.summarize_01b：按 clause
     「第五章<节号>」分组计数派生已全量/挂起节，根治①每全量一批口令行必
     漂移的顽疾；01b 缺失时返回 None 不炸）。

用法：python tests/test_stage1_regression.py   （退出码 0=全过，1=有失败）
依赖：零三方依赖（jsonschema 可选，不影响本测试）。
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
EMIT = ROOT / "skills" / "tender-document-review" / "scripts" / "emit_facts.py"
BUILD = ROOT / "skills" / "bid-response-plan" / "scripts" / "build_bid_plan.py"
VERIFY = ROOT / "skills" / "bid-response-plan" / "scripts" / "verify_format_chapters.py"
CONSIST = ROOT / "skills" / "bid-compliance-check" / "scripts" / "check_consistency.py"
FIXTURES = ROOT / "tests" / "fixtures"
HEADINGS = FIXTURES / "07_format_headings.sample-project.json"
EMIT_HEADINGS = ROOT / "skills" / "tender-document-review" / "scripts" / "emit_headings.py"
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "skills" / "bid-compliance-check" / "scripts"))
from check_01b_rawtext import check_items, load_units  # noqa: E402  （R4：01b 引文机检逻辑＋单元提取）
from check_compliance import summarize_01b  # noqa: E402  （R5：② 01b 覆盖口径动态派生）
sys.path.insert(0, str(ROOT / "skills" / "bid-response-plan" / "scripts"))
from parse_business_forms import BUSINESS_FORMS  # noqa: E402  （R2c：24 商务表名逐字锚定）

results = []  # (名称, 通过?, 详情)


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print("%s  %s%s" % ("PASS" if ok else "FAIL", name, ("　— " + detail) if detail and not ok else ""))


# 子进程输出钉死 UTF-8（N1 修复）：中文 Windows 默认 GBK 下，
# 子进程按 locale 写 GBK 而本进程按 encoding="utf-8" 解码会触发读线程
# UnicodeDecodeError（r.stderr 变 None → TypeError），故以 env 强制子进程
# PYTHONUTF8=1，errors="replace" 兜底防崩溃。无需宿主预设 PYTHONUTF8。
_ENV_UTF8 = dict(os.environ, PYTHONUTF8="1")


def run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run([PY] + [str(a) for a in args],
                          capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=_ENV_UTF8)


# ---------- R1：D5 加权闭合口径 ----------

def weighted_doc() -> dict:
    """加权型评分样本：商务/技术/价格各部分满分 100，权重 10%/40%/50%，总分 100。"""
    def item(sid, name, w):
        return {"id": sid, "item": name, "points": 100, "weight": w,
                "criteria": "", "subjective": False, "required_materials": "",
                "evidence": "", "gap": "", "owner": ""}
    return {
        "project": {"name": "回归用例", "no": "T-001", "purchaser": "某发包人"},
        "meta": {"doc_source_type": "招标", "business_type": "works", "submission_form": "电子"},
        "clauses": [],
        "scoring": {
            "total_stated": 100,
            "weight_basis": "商务10%+技术40%+价格50%（各100分，总分100）",
            "items": [item("S-01", "商务部分", 0.1), item("S-02", "技术部分", 0.4),
                      item("S-03", "价格部分", 0.5)],
        },
        "system_clues": [], "clarifications": [], "contacts": {}, "blind_format": {},
        "contract_deviations": [], "coverage_map": [],
    }


def r1_d5_weighted(tmp: Path) -> None:
    def emit(doc: dict, *cli: str) -> subprocess.CompletedProcess:
        p = tmp / "in.json"
        p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return run([EMIT, p, "-o", tmp / "out.json", *cli])

    # 1. CLI 录 100（＝加权合计）→ 闭合，无分值闭合告警；且结构校验必须通过
    r = emit(weighted_doc(), "--expected-total", "100")
    check("R1-1 加权口径闭合（--expected-total 100）",
          r.returncode == 0 and "分值闭合" not in r.stderr and "结构校验" not in r.stderr,
          "rc=%d stderr=%s" % (r.returncode, r.stderr[:200]))

    # 2. CLI 录 90 → 加权口径报差异 +10，并给出直接相加口径对照（3×100=300）
    r = emit(weighted_doc(), "--expected-total", "90")
    check("R1-2 加权口径差异（90）",
          r.returncode == 0 and "加权口径" in r.stderr and "差异 +10" in r.stderr
          and "直接相加口径合计为 300" in r.stderr,
          "rc=%d stderr=%s" % (r.returncode, r.stderr[:300]))

    # 3. 不传 CLI，回退读 scoring.total_stated=100 → 闭合
    r = emit(weighted_doc())
    check("R1-3 回退读 total_stated 闭合",
          r.returncode == 0 and "分值闭合" not in r.stderr,
          "rc=%d stderr=%s" % (r.returncode, r.stderr[:200]))

    # 4. 不传 CLI，total_stated=90 → 差异告警须注明「取自产物」
    doc = weighted_doc()
    doc["scoring"]["total_stated"] = 90
    r = emit(doc)
    check("R1-4 回退值差异注明来源",
          "取自产物 scoring.total_stated" in r.stderr and "差异 +10" in r.stderr,
          "rc=%d stderr=%s" % (r.returncode, r.stderr[:300]))

    # 5. 权重录成整数百分比（10/40/50）→ 加权合计 10000，告警须点名该成因
    doc = weighted_doc()
    for it in doc["scoring"]["items"]:
        it["weight"] = it["weight"] * 100
    r = emit(doc, "--expected-total", "100")
    check("R1-5 百分比误录点名（10 录为 10）",
          "录为 10" in r.stderr and "10000" in r.stderr,
          "rc=%d stderr=%s" % (r.returncode, r.stderr[:300]))

    # 6. 部分条目缺 weight（3 条仅 2 条带）→ 覆盖不全告警
    doc = weighted_doc()
    del doc["scoring"]["items"][2]["weight"]
    r = emit(doc, "--expected-total", "100")
    check("R1-6 加权覆盖不全告警",
          "仅 2 条带 weight" in r.stderr,
          "rc=%d stderr=%s" % (r.returncode, r.stderr[:300]))

    # 7. 缺 weight_basis → 依据不可追溯告警
    doc = weighted_doc()
    del doc["scoring"]["weight_basis"]
    r = emit(doc, "--expected-total", "100")
    check("R1-7 缺 weight_basis 告警",
          "未录 scoring.weight_basis" in r.stderr,
          "rc=%d stderr=%s" % (r.returncode, r.stderr[:300]))

    # 8. 加权型但总分两处皆无 → 未经闭合验算告警（不得静默通过）
    doc = weighted_doc()
    del doc["scoring"]["total_stated"]
    r = emit(doc)
    check("R1-8 加权型未录总分告警",
          "加权口径" in r.stderr and "未经闭合验算" in r.stderr,
          "rc=%d stderr=%s" % (r.returncode, r.stderr[:300]))


def r1_d5_direct(tmp: Path) -> None:
    """直接相加口径回归（v1.4.1 行为不得被加权改动破坏）。"""
    fx = json.loads((FIXTURES / "01_tender-facts.sample.json").read_text(encoding="utf-8"))
    total = sum(it["points"] for it in fx["scoring"]["items"])  # 10+20=30

    def emit(doc: dict, *cli: str) -> subprocess.CompletedProcess:
        p = tmp / "in2.json"
        p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return run([EMIT, p, "-o", tmp / "out2.json", *cli])

    r = emit(fx)
    check("R1-9 直接相加未录总分告警",
          "未经闭合验算" in r.stderr and "加权" not in r.stderr,
          "rc=%d stderr=%s" % (r.returncode, r.stderr[:200]))

    r = emit(fx, "--expected-total", str(total))
    check("R1-10 直接相加闭合（30）",
          r.returncode == 0 and "分值闭合" not in r.stderr,
          "rc=%d stderr=%s" % (r.returncode, r.stderr[:200]))

    r = emit(fx, "--expected-total", "100")
    check("R1-11 直接相加差异（-70）",
          "差异 -70" in r.stderr and "（加权口径）" not in r.stderr,
          "rc=%d stderr=%s" % (r.returncode, r.stderr[:300]))

    fx2 = json.loads(json.dumps(fx))
    fx2["scoring"]["total_stated"] = total
    r = emit(fx2)
    check("R1-12 直接相加回退 total_stated 闭合",
          r.returncode == 0 and "分值闭合" not in r.stderr,
          "rc=%d stderr=%s" % (r.returncode, r.stderr[:200]))


# ---------- R2：01c 章节树保真 ----------

def r2_format_chapters(tmp: Path) -> None:
    bid = tmp / "bid"
    bid.mkdir()
    shutil.copy(FIXTURES / "00_metadata.min.json", bid / "00_metadata.json")
    shutil.copy(FIXTURES / "01_tender-facts.sample.json", bid / "01_tender-facts.json")

    r = run([BUILD, "--bid", bid])
    ok_build = r.returncode == 0 and (bid / "01c_format-outline.json").is_file()
    check("R2-1 build_bid_plan.py 端到端生成（引用更新后 CID 全部可解析）",
          ok_build, "rc=%d stdout=%s stderr=%s" % (r.returncode, r.stdout[-300:], r.stderr[-300:]))
    if not ok_build:
        return

    r = run([VERIFY, "--01c", bid / "01c_format-outline.json", "--headings", HEADINGS])
    check("R2-2 01c 与原文格式章逐字一致（42 节点）",
          r.returncode == 0 and r.stdout.startswith("PASS"),
          "rc=%d stdout=%s" % (r.returncode, r.stdout[:400]))

    # 负例一：复刻历史缺陷形态（技术标 7→3 重排 + 删「（由投标人自行编制）」括号说明）。
    # 注意 3 在原文档他处存在（商务 3/价格 3），故归类为「章节名不符」而非「编号不存在」——
    # 两类归类都是检出，断言以实际归类为准。
    c01c = json.loads((bid / "01c_format-outline.json").read_text(encoding="utf-8"))
    for c in c01c["chapters"]:
        if c["id"] == "n-2103":
            c["number"] = "3"
        if c["id"] == "n-2102":
            c["title"] = "项目实施方案"
    bad = tmp / "01c_bad.json"
    bad.write_text(json.dumps(c01c, ensure_ascii=False), encoding="utf-8")
    r = run([VERIFY, "--01c", bad, "--headings", HEADINGS])
    check("R2-3 负例：历史缺陷形态（重排＋删括号）被检出",
          r.returncode == 1 and "章节名不符" in r.stdout and "括号说明被删" in r.stdout
          and "原文节点未收录" in r.stdout,
          "rc=%d stdout=%s" % (r.returncode, r.stdout[:400]))

    # 负例二：重排到原文档不存在的编号（12→13）→ 归类「疑似连续化重排」
    c01c = json.loads((bid / "01c_format-outline.json").read_text(encoding="utf-8"))
    for c in c01c["chapters"]:
        if c["id"] == "n-2108":
            c["number"] = "13"
    bad2 = tmp / "01c_bad2.json"
    bad2.write_text(json.dumps(c01c, ensure_ascii=False), encoding="utf-8")
    r = run([VERIFY, "--01c", bad2, "--headings", HEADINGS])
    check("R2-4 负例：编号不存在归类为疑似连续化重排",
          r.returncode == 1 and "疑似连续化重排" in r.stdout
          and "原文编号序列" in r.stdout,
          "rc=%d stdout=%s" % (r.returncode, r.stdout[:400]))


# ---------- R3：②-B 跨章一致性（check_consistency.py，全套件唯一实现） ----------

CONSIST_BID = {
    "schema_version": "0.1", "stage": "writing",
    "project": {"name": "示例发包人示例市100MW风电项目EPC总承包工程",
                "no": "ZB-DEMO-2026-001",
                "purchaser": "示例发包人示例市新能源有限公司"},
    "bid_mode": "normal", "deadline": "2026-11-10T09:30",
    "style_source": "tender_required",
}

CH_GOOD = ("# 投标函\n致：示例发包人示例市新能源有限公司\n"
           "我司参与示例发包人示例市100MW风电项目EPC总承包工程（招标编号：ZB-DEMO-2026-001）投标，\n"
           "投标总报价：12345.67万元，计划2026-12-01开工，2027-06-30全部机组并网发电。\n")
CH_AMOUNT = ("# 施工组织设计\n示例发包人示例市100MW风电项目EPC总承包工程计划 2026年12月1日开工，"
             "总工期 18 个月。\n本章涉及金额 12345.67万元；保证金 80万元。\n")
CH_BAD = ("# 商务偏差声明函\n针对示例发包人示例市100MW风电工程EPC总承包（招标编号写成 ZB-DEMO-2026-002）——\n"
          "本项目无偏差。\n")


def r3_consistency(tmp: Path) -> None:
    bid = tmp / "bid_consist"
    (bid / "05_chapters").mkdir(parents=True)
    (bid / "00_metadata.json").write_text(json.dumps(CONSIST_BID, ensure_ascii=False), encoding="utf-8")
    (bid / "05_chapters" / "03_bid.md").write_text(CH_GOOD, encoding="utf-8")
    (bid / "05_chapters" / "07_construct.md").write_text(CH_AMOUNT, encoding="utf-8")
    (bid / "05_chapters" / "09_dev.md").write_text(CH_BAD, encoding="utf-8")

    r = run([CONSIST, "--bid", bid])
    rep = (bid / "06_compliance" / "consistency-issues.md").read_text(encoding="utf-8") \
        if (bid / "06_compliance" / "consistency-issues.md").is_file() else ""
    check("R3-1 跨章一致性：变体/异值检出且 purchaser 与年份不误报（v0.4.0 起变体/异值升 ⚠️ 级）",
          r.returncode == 1 and "ZB-DEMO-2026-002" in rep
          and "风电工程EPC总承包" in rep
          and "新能源有限公司" not in rep.split("疑似变体")[-1].split("\n")[0]
          and "`2026`" not in rep and "`2027`" not in rep
          and "名称变体 1、编号异值 1、工期组 0、金额组 0" in r.stdout,
          "rc=%d stdout=%s" % (r.returncode, r.stdout[:300]))

    # 负例一：stage 非 writing → 拒跑（②-B 前置）
    meta2 = json.loads(json.dumps(CONSIST_BID)); meta2["stage"] = "plan_confirmed"
    (bid / "00_metadata.json").write_text(json.dumps(meta2, ensure_ascii=False), encoding="utf-8")
    r = run([CONSIST, "--bid", bid])
    check("R3-2 负例：stage 非 writing 拒跑", r.returncode == 2 and "writing" in (r.stdout + r.stderr),
          "rc=%d" % r.returncode)

    # 负例二：05_chapters 缺失 → 拒跑
    import shutil as _sh
    (bid / "00_metadata.json").write_text(json.dumps(CONSIST_BID, ensure_ascii=False), encoding="utf-8")
    _sh.rmtree(bid / "05_chapters")
    r = run([CONSIST, "--bid", bid])
    check("R3-3 负例：无 05_chapters 拒跑", r.returncode == 2 and "05_chapters" in (r.stdout + r.stderr),
          "rc=%d" % r.returncode)


# ---------- R4：① 01b 引文逐行机检（check_01b_rawtext.check_items 逻辑回归） ----------

RT_UNITS = {
    "P100": "本工程可利用率取全部机组缺陷责任期满时的平均值作为考核可利用率。"
            "最终验收的条件，全场风电机组可利用率不少于98%，单台风机的可利用率达到96%及以上。",
    "P200": "在缺陷责任期内，承包人对功率曲线的保证值应大于或等于保证功率曲线为基础计算出的"
            "风机发电量的97%，单台风机的功率曲线的保证值达到95%。",
    "P300": "所有涉及到的通信网络设备选用国产设备，操作系统必须选用 UNIX 等国产操作系统。",
    "P301": "所有涉及到的通信网络设备选用国产设备，操作系统必须选用 LINUX 等国产操作系统。",
    "T1R10": "1.3.3\t质量标准\t工程质量符合国家、行业现行规范标准，一次验收合格率100%。符合申报优质工程奖。",
}

def _item(sid, raw):
    return {"id": sid, "clause": "合成条款", "page": "n/a-无分页",
            "requirement": "合成要求", "required_value": "≥1", "unit": "个",
            "tolerance": "", "no_negative_allowed": True, "raw_text": raw}


def r4_01b_rawtext(tmp: Path) -> None:
    # 1. 照录（含省略号切片、次级锚点措辞差异、表格行锚点）→ 零失败
    good = [
        _item("sp-101", "全场风电机组可利用率不少于98%……（P100）"),
        _item("sp-102", "……单台风机的可利用率达到96%及以上。（P100）"),
        _item("sp-103", "承包人对功率曲线的保证值应大于或等于保证功率曲线为基础计算出的风机发电量的97%……（P200）"),
        _item("sp-104", "操作系统必须选用UNIX等国产操作系统。（P300；P301重申为LINUX）"),
        _item("sp-105", "一次验收合格率100%。（前附表1.3.3，T1R10）"),
    ]
    f = check_items(RT_UNITS, good)
    check("R4-1 01b 引文照录通过（省略号/次级锚点/表行锚点）", not f, "; ".join(f))

    # 2. 负例：改数值（98%→99%）→ 检出
    bad = [_item("sp-201", "全场风电机组可利用率不少于99%……（P100）")]
    f = check_items(RT_UNITS, bad)
    check("R4-2 负例：引文改数值被检出", f and "不在任何锚点" in f[0], "; ".join(f))

    # 3. 负例：无省略号静默截断（引文止于「风机发电量」，原文后续「的97%」）→ 检出
    bad = [_item("sp-202", "承包人对功率曲线的保证值应大于或等于保证功率曲线为基础计算出的风机发电量（P200）")]
    f = check_items(RT_UNITS, bad)
    check("R4-3 负例：无省略号截断被检出", f and "未落在原文边界" in f[0], "; ".join(f))

    # 4. 负例：锚点不存在（P999）→ 检出
    bad = [_item("sp-203", "全场风电机组可利用率不少于98%……（P999）")]
    f = check_items(RT_UNITS, bad)
    check("R4-4 负例：锚点不存在被检出", f and "不存在于原文" in f[0], "; ".join(f))

    # 5. 负例：id 重复 → 检出
    bad = [_item("sp-204", "全场风电机组可利用率不少于98%……（P100）"),
           _item("sp-204", "……单台风机的可利用率达到96%及以上。（P100）")]
    f = check_items(RT_UNITS, bad)
    check("R4-5 负例：id 重复被检出", f and "id 重复" in f[0], "; ".join(f))

    # 6. load_units 单元提取回归（v0.5.1 修复固化）：
    #    P 行正文含制表符 → 拼接样式之后全部字段；
    #    T 行末列为空、数据在非末列（示例市 T39 图纸资料分配表）→ 整行不丢；
    #    整行照录通过，错行照录被检出。
    dump = tmp / "synthetic_dump.txt"
    dump.write_text("P900\tHeading\t9.9\t图纸资料\n"
                    "T9R1\t1、施工图图纸\t6套\t\n"
                    "T9R2\t2、竣工图\t\t\n", encoding="utf-8")
    su = load_units(dump)
    check("R4-6a load_units：P 行正文含制表符时拼接样式后全部字段",
          su.get("P900") == "9.9\t图纸资料", repr(su.get("P900")))
    check("R4-6b load_units：T 行末列为空时非末列数据不丢（T39 缺口修复）",
          "6套" in su.get("T9R1", "") and "施工图图纸" in su.get("T9R1", ""),
          repr(su.get("T9R1")))
    good_t = [_item("sp-205", "1、施工图图纸6套（T9R1）")]
    f = check_items(su, good_t)
    check("R4-6c 表格行整行照录通过", not f, "; ".join(f))
    bad = [_item("sp-206", "2、竣工图6套（T9R1）")]
    f = check_items(su, bad)
    check("R4-6d 负例：表格行错行照录被检出", f and "不在任何锚点" in f[0], "; ".join(f))

    # 7. T 行单元格边界语义（v0.5.2 定型，固化两个真实缺陷）：
    #    a) 引文可自单元格边界起（跨前置单元格，如示例市 T1R10 末列含引文、
    #       前置列为编号/标准名称），且片段与单元同等归一化（半角括号→全角）；
    #    b) 单元格内非边界截断（无省略号删句）仍被检出。
    dump2 = tmp / "synthetic_dump2.txt"
    dump2.write_text("T8R1\t1.3.3\t质量标准\t工程质量符合(国家、行业现行有关设计、施工、验收规范标准)，一次验收合格率100%。符合申报优质工程奖。\n",
                     encoding="utf-8")
    su2 = load_units(dump2)
    ok = [_item("sp-207", "工程质量符合(国家、行业现行有关设计、施工、验收规范标准)，一次验收合格率100%。（T8R1）")]
    f = check_items(su2, ok)
    check("R4-7a T 行引文自单元格边界起并通过（含中英标点等价）", not f, "; ".join(f))
    bad = [_item("sp-208", "工程质量符合（T8R1）")]
    f = check_items(su2, bad)
    check("R4-7b 负例：T 行单元格内非边界截断被检出", f and "未落在原文边界" in f[0], "; ".join(f))


# ---------- R5：② 01b 覆盖口径动态派生（summarize_01b，根治硬编码计数漂移） ----------

# ---------- R2-5：① v0.24.0 派生任务卡·换项目真值回归 ----------

# 换项目真值条款（手造 8 条携带真实数值口径；其余 22 条以 ⑥ 合同类填充至 30 条）
# ——验证 ① 任务卡逐条派生：01 真值必须流入卡 notes，旧参考基硬编码必须缺位。
GZ_TRUE = [
    ("c-0001", "①时间节点与流程", "投标截止时间与递交", "投标截止时间为指定时间，逾期送达的不予受理", "否决投标"),
    ("c-0003", "⑤履约保证金与商务条款", "履约保证金", "履约保证金金额为500000元，形式为银行保函", "否则无效标"),
    ("c-0009", "②投标资格条件", "类似业绩", "自2021-01-01以来，至少1个投资额不低于10000万元的电力工程施工＋设计业绩", "否决投标"),
    ("c-0010", "②投标资格条件", "项目经理", "项目经理须为机电工程一级注册建造师，并持安全生产考核合格证（B证）", "否决投标"),
    ("c-0017", "④评标与定标标准", "评分权重", "评分权重为：技术22分、商务18分、报价60分", ""),
    ("c-0018", "④评标与定标标准", "评标基准价", "评标基准价J=(A×10%+B×60%+C×30%)×K，每偏离1%扣Q分", ""),
    ("c-0021", "③废标/否决情形", "下浮率", "报价下浮率大于10.00%的作无效标处理", "无效标"),
    ("c-0027", "⑦形式与程序要求", "横向暗标", "技术标采用横向暗标评审，不得出现投标人可识别标识", "否决投标"),
]
GZ_SCORES = [
    ("S-01", "技术文件完整性", 3), ("S-02", "设计管理", 2), ("S-03", "施工组织设计", 3),
    ("S-04", "质量管理", 2), ("S-05", "安全管理", 2), ("S-06", "环保管理", 3),
    ("S-07", "工期管理", 2), ("S-08", "资源投入", 2), ("S-09", "技术建议", 3),
    ("S-10", "投标人业绩", 10), ("S-11", "项目负责人业绩", 8),
    ("S-12", "施工工程费", 40), ("S-13", "运维费", 20),
]


def r2b_derived_cards(tmp: Path) -> None:
    # 以 fixtures 01 为底本（保 15 顶层必填字段过 validate_plan），替换 clauses/scoring
    bid = tmp / "bid-r25"
    bid.mkdir()
    shutil.copy(FIXTURES / "00_metadata.min.json", bid / "00_metadata.json")
    facts = json.loads((FIXTURES / "01_tender-facts.sample.json").read_text(encoding="utf-8"))
    true_ids = {g[0] for g in GZ_TRUE}
    clauses = []
    for i in range(1, 31):
        cid = "c-%04d" % i
        hit = next((g for g in GZ_TRUE if g[0] == cid), None)
        if hit:
            _, cat, item, text, cons = hit
        else:  # 填充条款：⑥ 合同类（business 且无澄清/事实缺口）
            cat, item = "⑥合同关键约束", "条款事项" + cid
            text, cons = "合成通用条款事项" + cid, ""
        clauses.append({
            "id": cid, "local_no": "9.%d" % i, "item": item, "category": cat,
            "review_stage": "responsive" if i % 2 else "form",
            "clause": "第二章 9.%d" % i, "page": "P1", "line": "L%d" % i,
            "text": text, "consequence": cons, "remark": "", "note": "",
            "price_cap_form": "amount" if cid == "c-0001" else "",
            "value_state": "stated",
        })
    facts["clauses"] = clauses
    facts["scoring"] = {"items": [
        {"id": s[0], "item": s[1], "points": s[2],
         "criteria": "合成评分标准", "subjective": s[0] not in ("S-12", "S-13"),
         "required_materials": "合成材料", "evidence": "待投标人提供",
         "gap": "", "owner": "合成组"} for s in GZ_SCORES]}
    (bid / "01_tender-facts.json").write_text(
        json.dumps(facts, ensure_ascii=False), encoding="utf-8")

    r = run([BUILD, "--bid", bid])
    check("R2-5a 派生卡端到端生成 rc==0（30 条款＋13 评分）",
          r.returncode == 0 and (bid / "03_bid-plan.json").is_file(),
          "rc=%d stdout=%s" % (r.returncode, r.stdout[-300:]))
    if r.returncode != 0:
        return
    plan = json.loads((bid / "03_bid-plan.json").read_text(encoding="utf-8"))
    items = plan["items"]
    check("R2-5b 卡数=67（30 条款＋24 表单＋13 评分）",
          len(items) == 67, "n=%d" % len(items))
    cov = plan.get("coverage", {})
    check("R2-5c coverage 全映射（mapped=13 unmapped=[]）",
          cov.get("mapped") == 13 and cov.get("unmapped") == []
          and cov.get("scoring_total") == 13, str(cov))
    notes = "\n".join(str(it.get("notes", "")) for it in items)
    for kw in ("500000", "10000万元", "2021-01-01", "一级注册建造师",
               "下浮率大于10.00%", "22分", "18分", "60分"):
        check("R2-5d 01 真值流入卡：%s" % kw, kw in notes)
    for bad in ("80万", "商务10%：响应性", "技术40%：施工总设", "价格50%：基准分90",
                "2022-2024", "基准分90/±1%"):
        check("R2-5e 旧参考基硬编码缺位：%s" % bad, bad not in notes)
    c01c = json.loads((bid / "01c_format-outline.json").read_text(encoding="utf-8"))
    tree_ids = {c["id"] for c in c01c["chapters"]}
    bad_ch = [it["id"] for it in items if it.get("chapter_id") not in tree_ids]
    check("R2-5f chapter_id 全部挂接 01c 章节树", not bad_ch, str(bad_ch[:5]))
    types = {it["source_type"] for it in items if it["source_ref"].startswith("c-")}
    check("R2-5g 类型派生（qualification/waste/business 三类并存）",
          types == {"qualification", "waste", "business"}, str(types))


# ---------- R2c：D1 章节树真实派生全链（Todo 10 第 3 批） ----------

def r2c_headings_real_derivation(tmp: Path) -> None:
    bid = tmp / "bid-d1"
    bid.mkdir()
    shutil.copy(FIXTURES / "00_metadata.min.json", bid / "00_metadata.json")
    shutil.copy(FIXTURES / "01_tender-facts.sample.json", bid / "01_tender-facts.json")

    # 合成树：3 个 level=1 组头（标题含槽关键词、异于常量树组名）＋24 表 name
    # 逐字（动态导入 BUSINESS_FORMS 取名防错字）＋1 条合成附加章（无
    # number/page，验派生默认值），共 28 条。
    def _fno(f):
        return int(f[0].rsplit("-", 1)[1])

    forms = sorted(BUSINESS_FORMS, key=_fno)
    names = {g: [f[1] for f in forms if _fno(f) in rng]
             for g, rng in (("biz", range(1, 19)), ("tech", (19,)), ("price", range(20, 25)))}
    heads = [{"title": "第一部分 商务文件", "level": 1, "number": "一", "page": "P1"}]
    heads += [{"title": t, "level": 2, "number": "B%d" % i, "page": "P%d" % i}
              for i, t in enumerate(names["biz"], 1)]
    heads.append({"title": "第二部分 技术文件", "level": 1, "number": "二", "page": "P1"})
    heads += [{"title": t, "level": 2, "number": "T%d" % i, "page": "P%d" % i}
              for i, t in enumerate(names["tech"], 1)]
    heads.append({"title": "合成技术附加章（回归测试专用）", "level": 2})
    heads.append({"title": "第三部分 价格文件", "level": 1, "number": "三", "page": "P1"})
    heads += [{"title": t, "level": 2, "number": "J%d" % i, "page": "P%d" % i}
              for i, t in enumerate(names["price"], 1)]
    n_total = len(heads)  # 3 组头＋24 表＋1 附加＝28

    draft = tmp / "draft_headings_d1.json"
    draft.write_text(json.dumps({"source": "R2c 合成回归", "headings": heads},
                                ensure_ascii=False), encoding="utf-8")

    # ⓪ emit_headings：契约自检＋溯源补齐＋条数守恒
    out_head = bid / "_headings_synth.json"
    r = run([EMIT_HEADINGS, draft, "-o", out_head, "--expected-headings", n_total])
    check("R2c-1 emit_headings rc==0＋写出＋溯源宣告（非 FALLBACK）",
          r.returncode == 0 and out_head.is_file() and "已写出" in r.stderr
          and "source_skill_version" in r.stderr and "FALLBACK" not in r.stderr,
          "rc=%d stderr=%s" % (r.returncode, r.stderr[-300:]))
    # 溯源字段与 ⓪ SKILL.md frontmatter 实读一致（防 FALLBACK 漂移）
    doc = json.loads(out_head.read_text(encoding="utf-8")) if out_head.is_file() else {}
    skill_md = (ROOT / "skills" / "tender-document-review" / "SKILL.md").read_text(encoding="utf-8")[:600]
    v_match = re.search(r"^version:\s*(\S+)\s*$", skill_md, re.M)
    check("R2c-2 溯源三件套（schema_version=0.1/rule_seq=10/版本=⓪ frontmatter 实读）",
          doc.get("schema_version") == "0.1" and doc.get("source_rule_seq") == 10
          and bool(v_match) and doc.get("source_skill_version") == v_match.group(1)
          and len(doc.get("headings", [])) == n_total,
          str({k: doc.get(k) for k in ("schema_version", "source_rule_seq", "source_skill_version")}))

    # emit 负例：结构校验 rc=1 ／ 条数不守恒 rc=2（两阻断路径均零产物）
    bad1 = tmp / "draft_headings_bad1.json"
    bad1.write_text(json.dumps({"headings": [{"title": "坏层级", "level": 0}]},
                               ensure_ascii=False), encoding="utf-8")
    r = run([EMIT_HEADINGS, bad1, "-o", tmp / "nope1.json"])
    check("R2c-3 emit 负例：level 非法 rc==1 且零产物",
          r.returncode == 1 and "level" in r.stderr and not (tmp / "nope1.json").is_file(),
          "rc=%d stderr=%s" % (r.returncode, r.stderr[-200:]))
    r = run([EMIT_HEADINGS, draft, "-o", tmp / "nope2.json", "--expected-headings", n_total + 1])
    check("R2c-4 emit 负例：条数不守恒 rc==2 且零产物",
          r.returncode == 2 and "不守恒" in r.stderr and not (tmp / "nope2.json").is_file(),
          "rc=%d stderr=%s" % (r.returncode, r.stderr[-200:]))

    # ① 真实派生：BUILD 消费 bid 根恰一份 _headings_*.json
    r = run([BUILD, "--bid", bid])
    check("R2c-5 build 真实派生 rc==0＋stdout 标记＋01c 落盘",
          r.returncode == 0 and "真实派生" in r.stdout
          and (bid / "01c_format-outline.json").is_file(),
          "rc=%d stdout=%s" % (r.returncode, r.stdout[-300:]))
    if r.returncode != 0:
        return
    chs = json.loads((bid / "01c_format-outline.json").read_text(encoding="utf-8"))["chapters"]
    titles = [c["title"] for c in chs]
    check("R2c-6 派生树形状（首条 n-1000／共 %d 条／组头 level=2 子条 level=3／缺页默认）" % n_total,
          bool(chs) and chs[0]["id"] == "n-1000" and len(chs) == n_total
          and all(c["level"] == 2 for c in chs if c["id"].endswith("000"))
          and all(c["level"] == 3 for c in chs if not c["id"].endswith("000"))
          and next(c for c in chs if c["title"] == "合成技术附加章（回归测试专用）")["page"] == "n/a-无分页",
          "first=%s n=%d" % (chs[0]["id"] if chs else "?", len(chs)))
    check("R2c-7 合成组名＋24 表名逐字在场（「投标函」异于常量树「投标函格式」）",
          "第一部分 商务文件" in titles and "第三部分 价格文件" in titles
          and all(t in titles for t in names["biz"] + names["tech"] + names["price"])
          and "投标函" in titles and "投标函格式" not in titles,
          str(titles[:6]))
    c03c = json.loads((bid / "03c_business-forms.json").read_text(encoding="utf-8"))
    tree_ids = {c["id"] for c in chs}
    bad_anchor = [f["id"] for f in c03c["forms"] if f.get("chapter_id") not in tree_ids]
    check("R2c-8 03c 24 表全部锚定派生树（chapter_id 在树内）",
          len(c03c["forms"]) == 24 and not bad_anchor,
          "n=%d bad=%s" % (len(c03c["forms"]), bad_anchor[:5]))

    # verify B 态（不传 --headings，01c 同目录自动发现恰一份）
    r = run([VERIFY, "--01c", bid / "01c_format-outline.json"])
    check("R2c-9 B 态派生重放逐字段一致",
          r.returncode == 0 and r.stdout.startswith("PASS") and "逐字段一致" in r.stdout,
          "rc=%d stdout=%s" % (r.returncode, r.stdout[:300]))
    c01c_bad = json.loads((bid / "01c_format-outline.json").read_text(encoding="utf-8"))
    for c in c01c_bad["chapters"]:
        if c["id"] == "n-1001":
            c["number"] = "9-手改"
    bad_01c = bid / "01c_bad_d1.json"  # 与恰一份 _headings_*.json 同目录 → 仍 B 态
    bad_01c.write_text(json.dumps(c01c_bad, ensure_ascii=False), encoding="utf-8")
    r = run([VERIFY, "--01c", bad_01c])
    check("R2c-10 负例：手改 01c 编号被 B 态重放检出（编号不符）",
          r.returncode == 1 and "编号不符" in r.stdout and "不一致" in r.stdout,
          "rc=%d stdout=%s" % (r.returncode, r.stdout[:300]))

    # 负例：多份 _headings_*.json → ① fail-loud 阻断（验后清理复原）
    shutil.copy(out_head, bid / "_headings_second.json")
    r = run([BUILD, "--bid", bid])
    check("R2c-11 负例：多份 _headings_*.json 阻断 build（rc==2）",
          r.returncode == 2 and "多份" in r.stdout,
          "rc=%d stdout=%s" % (r.returncode, r.stdout[:300]))
    (bid / "_headings_second.json").unlink()


def r5_summarize_01b(tmp: Path) -> None:
    # 合成 01b：第五章 2/3/8 节有条目（共 4 行）＋1 条非第五章条款＋9 节缺失
    def _it(sid, clause):
        return {"id": sid, "clause": clause, "page": "n/a-无分页",
                "requirement": "合成要求", "required_value": "≥98%", "unit": "%",
                "tolerance": "", "no_negative_allowed": True, "raw_text": "……（P3337）"}
    spec = tmp / "01b_spec-items.json"
    spec.write_text(json.dumps({
        "schema_version": "0.1",
        "source": {"file": "x", "page_range": "y"},
        "items": [_it("sp-001", "通用合同条款9.1.5"),
                  _it("sp-010", "第五章2.性能指标1）（1）"),
                  _it("sp-020", "第五章3.1.1基本要求"),
                  _it("sp-120", "第五章8.1.1高压电气设备现场试验项目"),
                  _it("sp-121", "第五章8.2.1总则")],
    }, ensure_ascii=False), encoding="utf-8")
    n, cov = summarize_01b(spec)
    check("R5-1 01b 覆盖口径动态派生（总数/已全量 3 节/挂起 6 节/第五章行数）",
          n == 5 and "已全量 3 节" in cov
          and "性能指标 1 行＋勘察设计 1 行＋竣工试验与验收 2 行" in cov
          and "共 4 行" in cov
          and "挂起 1.总则/4.施工安装/5.风电场调试、试运行和验收/6.施工工期"
          "/7.施工质量/9.工程管理" in cov,
          f"n={n} cov={cov}")
    n2, cov2 = summarize_01b(tmp / "not-exist.json")
    check("R5-2 负例：01b 缺失时返回 None 不炸（调用方走读取异常分支）",
          n2 is None and cov2 is None, f"n={n2}")


def main() -> int:
    if not HEADINGS.is_file():
        print("FAIL  缺 headings fixture：%s" % HEADINGS)
        return 1
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        r1_d5_weighted(tmp)
        r1_d5_direct(tmp)
        r2_format_chapters(tmp)
        r2b_derived_cards(tmp)
        r2c_headings_real_derivation(tmp)
        r3_consistency(tmp)
        r4_01b_rawtext(tmp)
        r5_summarize_01b(tmp)
    failed = [n for n, ok, _ in results if not ok]
    print("\n%s　%d 项通过 / %d 项失败" % ("PASS" if not failed else "FAIL",
          len(results) - len(failed), len(failed)))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
