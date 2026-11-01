#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pipeline_status.py — 投标全流程只读状态器（bid-pipeline 链首编排，零三方依赖）

用法：
    python scripts/pipeline_status.py --bid <项目bid目录>

做什么（只读，绝不写盘）：
  1. 读 <bid>/00_metadata.json（stage / bid_mode / deadline / failed_nodes /
     retry_count / warnings）；
  2. 按里程碑表核对已达标 stage 的产物在位性（口径同 tests/run_acceptance.py）；
  3. 打印：当前位置 → 模式/截止 → 章节进度（尽力而为）→ 产物在位性 →
     下一步技能＋动作＋关卡。

退出码：
  0 = 状态可判定（关卡停等 / 终态 / exhausted 转人工均属正常路由态）
  1 = 一致性异常：stage 已达标但里程碑产物缺件（回上游技能补齐或重跑）
  2 = 结构性阻断：--bid 缺失 / 目录不存在 / 00_metadata.json 缺失或不可解析 /
      stage 不在状态机枚举内（先执行 ⓪ tender-document-review）

状态机权威＝①②③④ 各自 references/流水线交接约定.md 四份逐字一致副本。
本脚本不复制其文本，只内嵌只读判定表；与 tests/run_acceptance.py 的口径
漂移由 tests/test_stage7_regression.py 交叉守护。
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

# ---------- 状态机（只读判定表；权威源＝流水线交接约定 §二） ----------
STAGE_ORDER = [
    "reviewed", "facts_confirmed", "planning", "plan_confirmed",
    "checking", "check_confirmed", "route_confirmed", "writing",
    "rechecking", "recheck_confirmed", "exported",
]

STAGE_LABEL = {
    "reviewed": "⓪ 审查完成",
    "facts_confirmed": "① 事实库已确认（G2 过）",
    "planning": "① 计划生成中",
    "plan_confirmed": "① 计划已确认（G1 过）",
    "checking": "②-A 覆盖检查执行中",
    "check_confirmed": "②-A 已确认（G3 过）",
    "route_confirmed": "③ 首章路线已确认（G4 过）",
    "writing": "③ 正文成文中",
    "rechecking": "②-B 成稿响应检查执行中",
    "recheck_confirmed": "②-B 已确认（G5 过）",
    "exported": "④ 导出完成",
    "exhausted": "重试耗尽（转人工）",
}

# 里程碑：stage 达标后必须存在的产物（相对 bid，支持 * 通配）。
# 形态与 tests/run_acceptance.py 的 IMPLIED 逐项一致（漂移守护锚点）。
MILESTONES = [
    ("⓪ 审查", "reviewed",
     ["00_metadata.json", "01_tender-facts.json"]),
    ("① 计划", "plan_confirmed",
     ["01b_spec-items.json", "01c_format-outline.json", "03_bid-plan.json",
      "03c_business-forms.json", "04_outline.json"]),
    ("②-A 覆盖检查", "checking",
     ["06_compliance/compliance-report.md", "06_compliance/compliance-report.json",
      "06_compliance/form-check.md"]),
    ("③ 正文", "route_confirmed", ["05_chapters/*.md"]),
    ("②-B 成稿响应", "rechecking", ["06_compliance/consistency-issues.md"]),
    ("④ 导出", "exported",
     ["07_out/投标文件.docx", "07_out/verify-report.md"]),
]

# 每个可读 stage 的下一步指路（技能＋动作＋关卡；停等话术见 SKILL.md §四）。
NEXT_ACTION = {
    "reviewed": ("① bid-response-plan",
                 "G2 前置：02_facts 项目事实快照逐项人工确认（缺则先建快照）→ ① 写 facts_confirmed"),
    "facts_confirmed": ("① bid-response-plan",
                        "计划生成段（任务卡＋目录骨架＋01b/01c/03c）→ G1 人工确认后 ① 写 plan_confirmed"),
    "planning": ("① bid-response-plan",
                 "计划生成中（继续 ① 至 G1 人工确认）"),
    "plan_confirmed": ("② bid-compliance-check（②-A）",
                       "覆盖检查 → compliance-report 逐条处置 → G3 人工确认后 ② 写 check_confirmed"),
    "checking": ("② bid-compliance-check（②-A）",
                 "覆盖检查执行中（继续 ② 至 G3 人工确认）"),
    "check_confirmed": ("③ bid-technical-proposal",
                        "首章五步循环 → 首章 G4 人工确认技术路线后 ③ 写 route_confirmed"),
    "route_confirmed": ("③ bid-technical-proposal",
                        "续章写作（每章动笔前各过一次 G4；全章 status=final 且 04 节点全 done 后交 ②-B）"),
    "writing": ("③ bid-technical-proposal",
                "未完章节继续；全部定稿 → ②-B 成稿响应检查（②-B 入口写 rechecking）"),
    "rechecking": ("② bid-compliance-check（②-B）",
                   "成稿响应检查执行中（含人工偏离表 08_business/deviation-table.md）"),
    "recheck_confirmed": ("④ bid-docx-export",
                          "导出链七脚本（样式档→证据索引→五项检查→PDF 装配→docx→元数据清理→回读校验）→ ④ 写 exported"),
    "exported": ("（终态）",
                 "链路收口：核对 07_out/verify-report.md 逐项结论＋人工终审后交付；无下一技能"),
    "exhausted": ("（转人工）",
                  "重试耗尽：人工处置 failed_nodes 后按流水线交接约定 §二 由责任技能重置 stage"),
}


def _block(bid, msg):
    print("【结构性阻断】" + msg)
    print("处置：先执行 ⓪ 招标文件审查（tender-document-review），产出 01_tender-facts.json 与 00_metadata.json")
    return 2


def _progress(bid):
    """章节进度（尽力而为：缺 04_outline.json 或不可解析时静默省略）。"""
    chapters = sorted(glob.glob(os.path.join(bid, "05_chapters", "*.md")))
    if not chapters:
        return ""
    try:
        with open(os.path.join(bid, "04_outline.json"), encoding="utf-8") as f:
            nodes = json.load(f).get("chapters", [])
    except (OSError, ValueError):
        nodes = []
    if nodes:
        done = sum(1 for n in nodes if isinstance(n, dict) and n.get("status") == "done")
        return "章节进度：%d/%d 节点 done（05_chapters 共 %d 文件）" % (done, len(nodes), len(chapters))
    return "章节进度：05_chapters 共 %d 文件（04_outline.json 不可读，无法算 done 占比）" % len(chapters)


def status(bid):
    """只读判定入口；返回退出码 0/1/2。"""
    meta_path = os.path.join(bid, "00_metadata.json")
    try:
        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)
    except OSError:
        return _block(bid, "00_metadata.json 不存在：%s" % meta_path)
    except ValueError:
        return _block(bid, "00_metadata.json 不可解析（JSON 语法错误）：%s" % meta_path)

    stage = meta.get("stage")
    if not isinstance(stage, str) or stage not in NEXT_ACTION:
        return _block(bid, "stage 缺失或不在状态机枚举内：实读 %r（期望之一：%s…）"
                      % (stage, "、".join(STAGE_ORDER[:3])))

    print("== 投标流水线状态（bid-pipeline 只读判定）==")
    proj = meta.get("project") or {}
    name = proj.get("name") if isinstance(proj, dict) else None
    if name:
        print("项目：%s" % name)
    print("阶段：%s（%s）" % (stage, STAGE_LABEL.get(stage, "?")))
    bits = []
    if meta.get("bid_mode"):
        bits.append("模式：%s" % meta["bid_mode"])
    if meta.get("deadline"):
        bits.append("截止：%s" % meta["deadline"])
    if bits:
        print("　".join(bits))
    prog = _progress(bid)
    if prog:
        print(prog)
    for key in ("retry_count", "failed_nodes", "warnings"):
        if meta.get(key):
            print("%s：%s" % (key, meta[key]))

    # 里程碑产物在位性（exhausted 不参与：其前序状态由责任技能维护）
    missing = []
    if stage in STAGE_ORDER:
        idx = STAGE_ORDER.index(stage)
        for label, mst, files in MILESTONES:
            if STAGE_ORDER.index(mst) > idx:
                continue
            for rel in files:
                if not glob.glob(os.path.join(bid, *rel.split("/"))):
                    missing.append("%s（%s 达标应有）" % (rel, mst))
    if missing:
        print("产物一致性：缺件 %d 项——%s" % (len(missing), "、".join(missing)))
        print("处置：stage 已达标但产物缺件——回上游技能补齐或重跑（只报告差异，不自动补猜）")
    else:
        print("产物一致性：里程碑产物全部在位")

    skill, action = NEXT_ACTION[stage]
    print("下一步：%s——%s" % (skill, action))
    return 1 if missing else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="投标全流程只读状态器（不写盘）")
    ap.add_argument("--bid", required=True, help="项目 bid 目录（含 00_metadata.json）")
    ns = ap.parse_args(argv)
    if not os.path.isdir(ns.bid):
        return _block(ns.bid, "--bid 目录不存在：%s" % ns.bid)
    return status(ns.bid)


if __name__ == "__main__":
    sys.exit(main())
