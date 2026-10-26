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

**入口闸门（v0.23.0 新增）**：SKILL.md §二 四步缺一即拒，形态对齐 ④ `_common.gate()`。
缺件/契约不符时输出「原因 → 缺少产物 → 处置」三段式并 rc=2、**零产物**（此前为抛
`FileNotFoundError`/`AssertionError` 栈回溯，虽同为非零退出，但无产品级指路）。

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


# ---------------- 入口闸门（SKILL.md §二 四步 / 流水线交接约定 L91） ----------------
BANNER = "【执行阻断】bid-response-plan（①）未执行"
EXPECT_CONTRACT = "0.4"          # 01_tender-facts.json 契约版本（等值校验）
CURRENT_SOURCE_SKILL = (1, 5, 1)  # ⓪ tender-document-review 当前版本

# 非 reviewed 状态下 stage 的归属，用于给出「下一步找谁」的指路（交接约定 L56–65）
STAGE_HINT = {
    "facts_confirmed": "① 自身流程态（G2 已通过）；如需重新总装，请人工将 stage 回退至 reviewed 后重试",
    "planning": "① 自身流程态（正在生成）；如需重新总装，请人工将 stage 回退至 reviewed 后重试",
    "plan_confirmed": "已过 G1，本步产物齐备；下一步是 ② bid-compliance-check 覆盖检查（②-A），无需重跑 ①",
    "checking": "② bid-compliance-check（②-A）执行中；补事实库请按其报告交 ①，不得直接重跑 ① 总装",
    "check_confirmed": "已过 G3，下一步 ③ bid-technical-proposal 写正文（首章先过 G4）",
    "route_confirmed": "③ bid-technical-proposal 写作中（已过首章 G4）",
    "writing": "③ bid-technical-proposal 写作中",
    "rechecking": "② bid-compliance-check（②-B）成稿检查执行中",
    "recheck_confirmed": "已过 G5，下一步 ④ bid-docx-export 导出",
    "exported": "④ 已导出完成；如需改产物请回退到对应阶段重做",
}


def _semver(s):
    """宽松解析 major.minor.patch；无法解析返回 None（不阻断，仅提示）。"""
    try:
        parts = [int(x) for x in str(s).strip().lstrip("vV").split(".")[:3]]
        while len(parts) < 3:
            parts.append(0)
        return tuple(parts[:3])
    except (ValueError, AttributeError):
        return None


def gate(bid):
    """① 入口闸门。返回 (rc, msgs)；rc=0 放行，rc=2 阻断（零产物）。

    四步（SKILL.md §二）：① 00_metadata 存在 → ② stage=reviewed →
    ③ 01 存在（缺即阻断，不得自行解析招标原文）、02_facts 可缺但显式告警 →
    ④ contract_schema_version 等值、source_skill_version semver 三档。
    """
    fails, warns = [], []

    if not os.path.isdir(bid):
        return 2, [BANNER,
                   f"原因：bid 目录不存在：{bid}",
                   "处置：先执行 ⓪ tender-document-review（招标解读），由其创建 bid 目录与 00_metadata.json"]

    meta_p = os.path.join(bid, "00_metadata.json")
    if not os.path.exists(meta_p):
        return 2, [BANNER,
                   "原因：缺 00_metadata.json（流水线状态载体，⓪ 出口产出）",
                   "处置：请先执行 ⓪ tender-document-review，产出 01_tender-facts.json 与 00_metadata.json"]
    try:
        with open(meta_p, encoding="utf-8") as f:
            meta = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return 2, [BANNER,
                   f"原因：00_metadata.json 不可解析：{e}",
                   "处置：重跑 ⓪ tender-document-review 修复该产物后重试"]

    stage = meta.get("stage")
    if stage != "reviewed":
        hint = STAGE_HINT.get(stage, f"未知 stage：{stage!r}（请核对 references/流水线交接约定.md 的 stage 表）")
        return 2, [BANNER,
                   f"原因：stage={stage!r}，① 要求 reviewed",
                   f"处置：{hint}"]

    p01 = os.path.join(bid, "01_tender-facts.json")
    if not os.path.exists(p01):
        return 2, [BANNER,
                   "原因：缺 01_tender-facts.json（单一真源；① 不得自行解析招标文件原文）",
                   "处置：请先执行 ⓪ tender-document-review 产出 01_tender-facts.json 后重试"]
    try:
        with open(p01, encoding="utf-8") as f:
            facts = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return 2, [BANNER,
                   f"原因：01_tender-facts.json 不可解析：{e}",
                   "处置：重跑 ⓪ tender-document-review 修复该产物后重试"]

    cv = facts.get("contract_schema_version")
    if cv != EXPECT_CONTRACT:
        fails.append(f"01_tender-facts.json 契约版本不符：contract_schema_version={cv!r}（要求 {EXPECT_CONTRACT!r}）")

    sv = _semver(facts.get("source_skill_version"))
    if sv is None:
        warns.append(f"source_skill_version 缺失或不可解析（{facts.get('source_skill_version')!r}），无法做版本档位判断")
    else:
        cur = CURRENT_SOURCE_SKILL
        if sv[0] != cur[0]:
            fails.append(f"source_skill_version={'.'.join(map(str, sv))} 与当前 ⓪ v{'.'.join(map(str, cur))} "
                         f"major 不一致（跨大版本，01 需重抽取）")
        elif sv[1] != cur[1]:
            warns.append(f"source_skill_version={'.'.join(map(str, sv))} 与当前 ⓪ v{'.'.join(map(str, cur))} "
                         f"minor 不一致（上游有功能更新，建议确认是否需重抽取 01）")
        # patch 差异：静默

    if not any(os.path.exists(os.path.join(bid, n))
               for n in ("02_facts.md", "02_facts.yaml", "02_facts.json")):
        warns.append("缺 02_facts.(md|yaml|json)——全部任务卡将置 blocked_by_facts"
                     "（铁律：不得按「默认就绪」处理，不得代填事实库）")

    msgs = fails + [f"⚠️ {w}" for w in warns]
    return (2 if fails else 0), msgs


def main():
    ap = argparse.ArgumentParser(description="① 产物总装：01c/03/04/03c/01b + 素材缺口清单")
    ap.add_argument("--bid", required=True, help="项目 bid 目录")
    args = ap.parse_args()
    bid = args.bid

    rc, msgs = gate(bid)
    for m in msgs:
        print(m)
    if rc != 0:
        return rc  # 缺件/契约不符：阻断，零产物

    meta = load_json(os.path.join(bid, "00_metadata.json"))
    facts = load_json(os.path.join(bid, "01_tender-facts.json"))

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
    return 1 if failed else 0


if __name__ == "__main__":
    # 退出码：0=通过；1=契约校验失败（产物已写，需处置）；2=入口缺件/契约不符（零产物）
    sys.exit(main())
