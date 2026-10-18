# -*- coding: utf-8 -*-
"""
build_bid_plan.py —— ① bid-response-plan 主编排器（v0.3.0）
计划书 §4.1（M1 任务卡）/ 计划书 §4.2（M3 目录骨架）/ 计划书 §6.2（契约）。

本文件是**总装编排**：按顺序调用五个专职脚本（计划书 §5 目录树）——
  parse_format_outline.py   → 01c_format-outline.json   （格式章章节树＋排版）
  parse_spec_items.py       → 01b_spec-items.json       （技术规范条目抄行）
  parse_business_forms.py   → 03c_business-forms.json   （商务表框架，无金额）
  build_task_cards.py       → 03_bid-plan.json / 04_outline.json / 素材缺口清单.md
  validate_plan.py          → 全部产物的契约校验（只报告，不修改）
输入：00_metadata.json(stage=reviewed) + 01_tender-facts.json(契约0.4)
用法：python build_bid_plan.py --bid <项目>/bid

🔴 保真规则（v0.3.0 加固，验收记录 #2 实测缺陷）：编号与章节名**逐字照录**——
   ① 原文档编号不连续时（如技术标 1、2、7–12）**不得连续化重排**；
   ② 章节名中的括号说明（如「项目实施方案（由投标人自行编制）」）**不得删除**；
   ③ 换项目覆盖常量后，必须跑 scripts/verify_format_chapters.py 与抽取结果比对，
      全部逐字一致方可采用（机检，不靠肉眼）。
"""
import argparse, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from parse_format_outline import build_01c
from parse_spec_items import build_01b
from parse_business_forms import build_03c
from build_task_cards import build_03, build_04, build_gap_md, load_json
import validate_plan


def w(bid, name, obj):
    p = os.path.join(bid, name)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    return p


def main():
    ap = argparse.ArgumentParser(description="① 产物总装：01c/03/04/03c/01b + 素材缺口清单")
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

    p1 = w(bid, "01c_format-outline.json", c01c)
    p3 = w(bid, "03_bid-plan.json", c03)
    p4 = w(bid, "04_outline.json", c04)
    p3c = w(bid, "03c_business-forms.json", c03c)
    p1b = w(bid, "01b_spec-items.json", c01b)
    pgap = os.path.join(bid, "素材缺口清单.md")
    with open(pgap, "w", encoding="utf-8") as f:
        f.write(build_gap_md(c03))

    print("OK 产出：")
    for p in (p1, p3, p4, p3c, p1b):
        print("  ", p)
    print("   ", pgap)
    print("契约校验：")
    # 直接调内部函数，避免 argparse 二次解析 sys.argv
    failed = False
    for k in validate_plan.TARGETS:
        res, hard = validate_plan.validate_one(bid, k)
        if hard:
            failed = True
        print("  %-4s %-26s %s" % (k, validate_plan.TARGETS[k][0], res))
    print("任务卡数：", len(c03["items"]), "unmapped：", c03["coverage"]["unmapped"])
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
