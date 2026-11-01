#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/test_stage7_regression.py — 阶段 7（bid-pipeline 链首编排）永久回归

覆盖（repo/v1.7.45）：
  T7-1 pipeline_status.py 合成工作区八例：空目录/坏 JSON/未知 stage → rc2 结构性阻断；
     reviewed 全在位 → rc0 下一步①；reviewed 缺 01 → rc1 缺件；exported 全产物树 →
     rc0 终态全部在位；exhausted → rc0 转人工＋failed_nodes 透传；writing＋blind＋
     截止日期＋outline 进度 → rc0（1/2 节点）。
  T7-2 触发短语自检：六技能触发集无碰撞；① 恰注册六短语（三让渡短语不回流）；
     bid-pipeline 恰注册三短语；其余四技能触发集打印供人工复核（无测试断言）。
  T7-3 防漂移对照：pipeline_status 与 run_acceptance 状态机口径直接全等——
     STAGE_ORDER == ra.STAGE_ORDER、MILESTONES == ra.IMPLIED（run_acceptance 无
     MILESTONES，IMPLIED 即 ④ 端到端链里程碑单源，两处任一漂移即 FAIL）。
  T7-4 链外编排口径：validate_contract.FIVE 含 bid-pipeline 而 FOUR 不含
     （C3/C4/C9/C10 四检查不覆盖编排技能，口径即契约）。

用法：python tests/test_stage7_regression.py（退出码 0=全过，1=有失败）
依赖：零三方依赖。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PS = ROOT / "skills" / "bid-pipeline" / "scripts" / "pipeline_status.py"

SIX = [
    "tender-document-review",
    "bid-response-plan",
    "bid-compliance-check",
    "bid-technical-proposal",
    "bid-docx-export",
    "bid-pipeline",
]
EXPECT_PLAN = {
    "帮我编标书", "投标文件怎么写", "看还缺什么材料",
    "排投标目录", "生成投标任务卡", "投标响应策划",
}
EXPECT_PIPELINE = {"帮我写投标文件", "帮我做投标文件", "做这个标"}

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print("%s  %s%s" % ("PASS" if ok else "FAIL", name,
                        ("　— " + detail) if detail and not ok else ""))


def run_py(script, args):
    p = subprocess.run([sys.executable, "-X", "utf8", str(script)] + args,
                       capture_output=True, text=True, encoding="utf-8")
    return p.returncode, p.stdout + p.stderr


def wjson(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")


def case_dir(tmp, name):
    d = tmp / name
    d.mkdir(parents=True)
    return d


FIVE_PLAN_JSON = ["01b_spec-items.json", "01c_format-outline.json", "03_bid-plan.json",
                  "03c_business-forms.json", "04_outline.json"]


def main():
    tmp = Path(tempfile.mkdtemp(prefix="s7_"))
    try:
        # ---------- T7-1 pipeline_status 合成工作区八例 ----------
        c1 = case_dir(tmp, "c1")
        rc, out = run_py(PS, ["--bid", str(c1)])
        check("T7-1 c1 空目录 → rc2 结构性阻断",
              rc == 2 and "结构性阻断" in out, "rc=%d" % rc)

        c2 = case_dir(tmp, "c2")
        (c2 / "00_metadata.json").write_text("{oops", encoding="utf-8")
        rc, out = run_py(PS, ["--bid", str(c2)])
        check("T7-1 c2 坏 JSON → rc2 结构性阻断",
              rc == 2 and "结构性阻断" in out, "rc=%d" % rc)

        c3 = case_dir(tmp, "c3")
        wjson(c3 / "00_metadata.json", {"stage": "reviewed",
                                        "project": {"name": "样例风电EPC"},
                                        "bid_mode": "normal"})
        wjson(c3 / "01_tender-facts.json", {})
        rc, out = run_py(PS, ["--bid", str(c3)])
        check("T7-1 c3 reviewed 全在位 → rc0 下一步①",
              rc == 0 and "bid-response-plan" in out and "全部在位" in out,
              "rc=%d" % rc)

        c4 = case_dir(tmp, "c4")
        wjson(c4 / "00_metadata.json", {"stage": "reviewed"})
        rc, out = run_py(PS, ["--bid", str(c4)])
        check("T7-1 c4 reviewed 缺 01 → rc1 缺件",
              rc == 1 and "缺件" in out and "01_tender-facts.json" in out,
              "rc=%d" % rc)

        c5 = case_dir(tmp, "c5")
        wjson(c5 / "00_metadata.json", {"stage": "exported"})
        wjson(c5 / "01_tender-facts.json", {})
        for fn in FIVE_PLAN_JSON:
            wjson(c5 / fn, {})
        comp = c5 / "06_compliance"
        comp.mkdir()
        for fn in ["compliance-report.md", "compliance-report.json",
                   "form-check.md", "consistency-issues.md"]:
            (comp / fn).write_text("x", encoding="utf-8")
        ch = c5 / "05_chapters"
        ch.mkdir()
        (ch / "n-1001.md").write_text("x", encoding="utf-8")
        outdir = c5 / "07_out"
        outdir.mkdir()
        (outdir / "投标文件.docx").write_bytes(b"x")
        (outdir / "verify-report.md").write_text("x", encoding="utf-8")
        rc, out = run_py(PS, ["--bid", str(c5)])
        check("T7-1 c5 exported 全产物树 → rc0 终态",
              rc == 0 and "终态" in out and "全部在位" in out, "rc=%d" % rc)

        c6 = case_dir(tmp, "c6")
        wjson(c6 / "00_metadata.json", {"stage": "exhausted",
                                        "failed_nodes": ["n-0801"]})
        rc, out = run_py(PS, ["--bid", str(c6)])
        check("T7-1 c6 exhausted → rc0 转人工＋failed_nodes 透传",
              rc == 0 and "转人工" in out and "n-0801" in out, "rc=%d" % rc)

        c7 = case_dir(tmp, "c7")
        wjson(c7 / "00_metadata.json", {"stage": "flying"})
        rc, out = run_py(PS, ["--bid", str(c7)])
        check("T7-1 c7 未知 stage → rc2 结构性阻断",
              rc == 2 and "结构性阻断" in out, "rc=%d" % rc)

        c8 = case_dir(tmp, "c8")
        wjson(c8 / "00_metadata.json", {"stage": "writing", "bid_mode": "blind",
                                        "deadline": "2026-11-08T10:00:00+08:00"})
        wjson(c8 / "01_tender-facts.json", {})
        for fn in FIVE_PLAN_JSON:
            wjson(c8 / fn, {})
        wjson(c8 / "04_outline.json",
              {"chapters": [{"id": "n-1001", "status": "done"},
                            {"id": "n-1002", "status": "todo"}]})
        comp = c8 / "06_compliance"
        comp.mkdir()
        for fn in ["compliance-report.md", "compliance-report.json", "form-check.md"]:
            (comp / fn).write_text("x", encoding="utf-8")
        ch = c8 / "05_chapters"
        ch.mkdir()
        (ch / "n-1001.md").write_text("x", encoding="utf-8")
        rc, out = run_py(PS, ["--bid", str(c8)])
        check("T7-1 c8 writing＋blind＋截止日期＋outline 进度 → rc0（1/2 节点）",
              rc == 0 and "1/2 节点" in out and "blind" in out
              and "2026-11-08" in out, "rc=%d" % rc)

        # ---------- T7-2 触发短语自检 ----------
        sys.path.insert(0, str(ROOT / "tests"))
        import validate_contract as vc
        descs = {s: vc.description(s) for s in SIX}
        seen = {}
        collisions = []
        for s in SIX:
            for t in vc.triggers(descs[s]):
                if t in seen and seen[t] != s:
                    collisions.append((t, seen[t], s))
                seen[t] = s
        check("T7-2 六技能触发短语无碰撞", not collisions,
              "collisions=%s" % (collisions,))
        t_plan = vc.triggers(descs["bid-response-plan"])
        check("T7-2 ① 恰注册六短语（三让渡短语不回流）",
              t_plan == EXPECT_PLAN,
              "extra=%s missing=%s" % (sorted(t_plan - EXPECT_PLAN),
                                       sorted(EXPECT_PLAN - t_plan)))
        t_pipe = vc.triggers(descs["bid-pipeline"])
        check("T7-2 pipeline 恰注册三短语",
              t_pipe == EXPECT_PIPELINE,
              "extra=%s missing=%s" % (sorted(t_pipe - EXPECT_PIPELINE),
                                       sorted(EXPECT_PIPELINE - t_pipe)))
        for s in ["tender-document-review", "bid-compliance-check",
                  "bid-technical-proposal", "bid-docx-export"]:
            print("  [人工复核] %s 触发集：%s"
                  % (s, sorted(vc.triggers(descs[s]))))

        # ---------- T7-3 防漂移对照 ----------
        sys.path.insert(0, str(ROOT / "skills" / "bid-pipeline" / "scripts"))
        import pipeline_status as psm
        import run_acceptance as ra
        check("T7-3 STAGE_ORDER 与 run_acceptance 全等",
              psm.STAGE_ORDER == ra.STAGE_ORDER,
              "ps=%s ra=%s" % (psm.STAGE_ORDER, ra.STAGE_ORDER))
        diff = set(map(str, psm.MILESTONES)) ^ set(map(str, ra.IMPLIED))
        check("T7-3 MILESTONES 与 ra.IMPLIED 全等（里程碑单源）",
              psm.MILESTONES == ra.IMPLIED and not diff,
              "diff=%s" % (sorted(diff),))

        # ---------- T7-4 链外编排口径 ----------
        check("T7-4 FIVE 含 bid-pipeline（六技能名册）",
              "bid-pipeline" in vc.FIVE, "FIVE=%s" % (vc.FIVE,))
        check("T7-4 FOUR 不含 bid-pipeline（C3/C4/C9/C10 不覆盖编排）",
              "bid-pipeline" not in vc.FOUR and set(vc.FOUR) <= set(vc.FIVE),
              "FOUR=%s" % (vc.FOUR,))

        bad = [n for n, ok, _ in results if not ok]
        print("\n阶段 7 回归：%d 项，失败 %d 项" % (len(results), len(bad)))
        if bad:
            for n in bad:
                print("  FAIL:", n)
        return 0 if not bad else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
