#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/test_stage1_regression.py — v0.16 阶段 1 验收 P0 两项修复的永久回归

覆盖（对应验收记录第五节优先级表 P0×2 + P1）：
  R1 ⓪ D5 加权闭合口径：tender-facts.schema.json 三新字段
     （scoring.total_stated / scoring.weight_basis / scoring.items[].weight）
     + emit_facts.py 两种口径（直接相加 / 加权闭合）验算与回退逻辑；
  R2 ① 01c 章节树保真：FORMAT_CHAPTERS 与原文第七章逐字一致（编号不重排、
     括号说明不删），经 build_bid_plan.py 端到端生成后由
     verify_format_chapters.py 机检（含负例：重排＋删括号必须被检出）；
  R4 ① 01b 引文逐行机检（check_01b_rawtext.check_items 逻辑回归，合成数据：
     照录通过；改数值/无省略号截断/锚点不存在必须被检出）。

用法：python tests/test_stage1_regression.py   （退出码 0=全过，1=有失败）
依赖：零三方依赖（jsonschema 可选，不影响本测试）。
"""
from __future__ import annotations

import json
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
HEADINGS = FIXTURES / "07_format_headings.shenzhou.json"
sys.path.insert(0, str(ROOT / "tests"))
from check_01b_rawtext import check_items  # noqa: E402  （R4：01b 引文机检逻辑）

results = []  # (名称, 通过?, 详情)


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print("%s  %s%s" % ("PASS" if ok else "FAIL", name, ("　— " + detail) if detail and not ok else ""))


def run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run([PY] + [str(a) for a in args],
                          capture_output=True, text=True, encoding="utf-8")


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
    check("R2-2 01c 与原文第七章逐字一致（42 节点）",
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
    "project": {"name": "中能建投深州100MW风电项目EPC总承包工程",
                "no": "ZJL-SZ-2026-018",
                "purchaser": "中能建投深州新能源有限公司"},
    "bid_mode": "normal", "deadline": "2026-11-10T09:30",
    "style_source": "tender_required",
}

CH_GOOD = ("# 投标函\n致：中能建投深州新能源有限公司\n"
           "我司参与中能建投深州100MW风电项目EPC总承包工程（招标编号：ZJL-SZ-2026-018）投标，\n"
           "投标总报价：12345.67万元，计划2026-12-01开工，2027-06-30全部机组并网发电。\n")
CH_AMOUNT = ("# 施工组织设计\n中能建投深州100MW风电项目EPC总承包工程计划 2026年12月1日开工，"
             "总工期 18 个月。\n本章涉及金额 12345.67万元；保证金 80万元。\n")
CH_BAD = ("# 商务偏差声明函\n针对中能建投深州100MW风电工程EPC总承包（招标编号写成 ZJL-SZ-2026-019）——\n"
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
    check("R3-1 跨章一致性：变体/异值检出且 purchaser 与年份不误报",
          r.returncode == 0 and "ZJL-SZ-2026-019" in rep
          and "风电工程EPC总承包" in rep
          and "新能源有限公司" not in rep.split("疑似变体")[-1].split("\n")[0]
          and "`2026`" not in rep and "`2027`" not in rep,
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


def main() -> int:
    if not HEADINGS.is_file():
        print("FAIL  缺 headings fixture：%s" % HEADINGS)
        return 1
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        r1_d5_weighted(tmp)
        r1_d5_direct(tmp)
        r2_format_chapters(tmp)
        r3_consistency(tmp)
        r4_01b_rawtext(tmp)
    failed = [n for n, ok, _ in results if not ok]
    print("\n%s　%d 项通过 / %d 项失败" % ("PASS" if not failed else "FAIL",
          len(results) - len(failed), len(failed)))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
