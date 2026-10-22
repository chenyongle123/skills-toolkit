# -*- coding: utf-8 -*-
"""
run_acceptance.py —— 五技能链端到端阶段验收驱动器（阶段 4；计划书 §5 目录树 / §11）
================================================================================
核查模式（默认，只读）：产物清点、stage↔产物一致性、只读校验器（① validate_plan／
③ check_facts／③ word_count）、暗标套件级标识扫描（bid_mode=blind ×
01c.identity_ban）、当前可达边界（frontier）与下一步处置指引。

串联模式（--run，会改写产物与 00_metadata.stage）：从当前 stage 把机器可执行段
全部推进，在人工关卡（G1–G5）与内容环节（⓪ 审查／③ 写作／②-B 人工偏离表）停住。
数据安全（AGENTS.md）：--run 仅用于 workdir/acceptance/ 副本，勿对用户工程目录运行。

用法：
  python tests/run_acceptance.py --bid <bid目录>
  python tests/run_acceptance.py --bid <bid目录> --run
  python tests/run_acceptance.py --bid <bid目录> --json <报告路径>

退出码：0＝可达范围内全部通过；1＝存在 FAIL／不一致／步骤失败；2＝结构性阻断。
零三方依赖；Python ≥ 3.8。
"""
from __future__ import annotations

import argparse
import datetime as _dt
import glob
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable or "python"

# ---------- 流水线 stage 机（交接约定 §二；四技能副本逐字一致） ----------
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

# stage 达标后必须存在的产物（相对 bid，支持 * 通配）；缺件＝一致性 FAIL
IMPLIED = [
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

GATE_HELP = {
    "G2": "① G2（人工）：事实库完整准确逐项确认后写 stage=facts_confirmed",
    "G1": "① G1（人工）：章节名/顺序/篇幅分配确认后写 stage=plan_confirmed",
    "G3": "② G3（人工）：compliance-report.md 的响应不足/未响应/需原件核对项"
          "逐条处置后写 stage=check_confirmed",
    "G4": "③ G4（人工）：首章技术路线确认为企业真实采用后写 stage=route_confirmed"
          "（后续章保持 writing）",
    "G5": "② G5（人工）：背对背复核差异闭环/跨章一致/暗标终检通过后写 stage=recheck_confirmed",
}

# ④ 导出链（④ SKILL §三：七脚本按序，统一 --bid；rc 非 0 即停并给语义注记）
EXPORT_CHAIN = [
    ("build_style_profile.py", "④.1 build_style_profile（样式档）",
     "rc=2＝01c 缺失/不可解析"),
    ("index_evidence.py", "④.2 index_evidence（证据索引）",
     "rc=2＝evidence/ 缺失或为空"),
    ("check_evidence.py", "④.3 check_evidence（证据五项检查）",
     "rc=1＝存在错误项（装配前须闭环）；rc=2＝缺 03b"),
    ("assemble_pdf.py", "④.4 assemble_pdf（含附件 PDF 装配）",
     "rc=1＝装配错误/超页数上限；rc=2＝前置缺失/闸门阻断"),
    ("export_docx.py", "④.5 export_docx（docx 生成）",
     "rc=1＝生成错误；rc=2＝前置缺失/闸门阻断（零产物）"),
    ("scrub_metadata.py", "④.6 scrub_metadata（元数据清洁）",
     "rc=1＝修订记录/暗标标识命中须人工处置；rc=2＝缺 docx"),
    ("verify_docx.py", "④.7 verify_docx（回读校验→exported）",
     "rc=1＝残留/不符；rc=2＝前置缺失"),
]

# 产物清点分组（信息态展示；一致性判据用上方 IMPLIED）
INVENTORY_GROUPS = [
    ("⓪ 审查", ["00_metadata.json", "01_tender-facts.json", "02_facts.md", "02_facts.yaml"]),
    ("① 计划", ["01b_spec-items.json", "01c_format-outline.json", "03_bid-plan.json",
                "03c_business-forms.json", "04_outline.json", "素材缺口清单.md"]),
    ("② 合规", ["06_compliance/compliance-report.md", "06_compliance/compliance-report.json",
                "06_compliance/form-check.md", "06_compliance/deviation-table.md",
                "06_compliance/business-check.md", "06_compliance/consistency-issues.md",
                "06_compliance/evidence-check.md"]),
    ("③ 正文", ["05_chapters/*.md"]),
    ("②-B 人工", ["08_business/deviation-table.md"]),
    ("④ 证据", ["03b_evidence-index.json", "evidence/*"]),
    ("④ 导出", ["07_out/style-profile.yaml", "07_out/投标文件.docx",
                "07_out/投标文件_含附件.pdf", "07_out/pagination.json",
                "07_out/verify-report.md"]),
]


# ---------- 小工具 ----------
def _S(skill, script):
    """技能脚本的仓库内绝对路径。"""
    return os.path.join(REPO, "skills", skill, "scripts", script)


def _expand(bid, rel):
    """按相对路径（支持 * 通配）取已存在文件列表。"""
    return sorted(glob.glob(os.path.join(bid, *rel.split("/"))))


def _missing(bid, rels):
    """返回仍无任何命中文件的相对路径列表。"""
    return [r for r in rels if not _expand(bid, r)]


def _sh(script, bid, extra=()):
    """以 UTF-8 子进程跑技能脚本（统一 --bid），返回 (rc, 输出行列表)。"""
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    argv = [PY, script] + list(extra) + ["--bid", bid]
    p = subprocess.run(argv, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env)
    lines = ((p.stdout or "") + (p.stderr or "")).strip().splitlines()
    return p.returncode, lines


def _tail(lines, n=3):
    return " ⏎ ".join(lines[-n:]) if lines else "(无输出)"


def _stage(bid):
    """实读当前 stage（②-B/④ 脚本会改写 00_metadata）。"""
    try:
        with open(os.path.join(bid, "00_metadata.json"), encoding="utf-8") as f:
            return json.load(f).get("stage", "")
    except (OSError, ValueError):
        return ""


def _chapters(bid):
    return _expand(bid, "05_chapters/*.md")


def _load_meta(bid):
    with open(os.path.join(bid, "00_metadata.json"), encoding="utf-8") as f:
        return json.load(f)


def frontier_of(bid, stage):
    """可达边界判定：(当前段, 为什么停, 下一步动作)。两模式共用。"""
    if stage == "exhausted":
        return ("exhausted", "回退重试耗尽", "人工处置后重置 stage 再跑")
    if stage not in STAGE_ORDER:
        return ("未知", "stage=%r 不在状态机枚举内" % stage, "人工核对 00_metadata.json")
    if stage == "reviewed":
        if _missing(bid, ["01_tender-facts.json"]):
            return ("⓪ 审查", "01_tender-facts.json 缺失", "先执行 ⓪ 招标解读")
        return ("① 关卡 G2＋G1", "事实库与计划待人工确认", "确认后写 facts_confirmed→plan_confirmed")
    if stage in ("facts_confirmed", "planning"):
        return ("① 关卡 G1", "目录骨架待人工确认", GATE_HELP["G1"])
    if stage in ("plan_confirmed", "checking"):
        return ("② 关卡 G3", "废标报告处置待人工完成", GATE_HELP["G3"])
    if stage == "check_confirmed":
        if not _chapters(bid):
            return ("③ 写作（内容环节）", "05_chapters/ 无成稿",
                    "③ 五步循环逐章成稿（每章动笔前过 G4）")
        return ("③ 关卡 G4", "首章已成稿，技术路线待人工确认", GATE_HELP["G4"])
    if stage == "route_confirmed":
        return ("③ 写作（内容环节）", "首章已确认，后续章写作中",
                "全部章节 status: final 后写 stage=writing")
    if stage == "writing":
        if not _chapters(bid):
            return ("③ 写作（内容环节）", "05_chapters/ 无成稿", "③ 逐章成稿")
        if not _expand(bid, "08_business/deviation-table.md"):
            return ("②-B 前置（人工落点）", "08_business/deviation-table.md 缺失",
                    "按 ② SKILL §②-B：首列=01b 条目id（sp-xxx）逐行对齐填写")
        return ("②-B 成稿响应检查", "待跑", "check_compliance --mode B ＋ check_consistency")
    if stage == "rechecking":
        return ("② 关卡 G5", "成稿终检待人工确认", GATE_HELP["G5"])
    if stage == "recheck_confirmed":
        return ("④ 导出链", "待跑", "七脚本按序执行（④ SKILL §三）")
    return ("链路终点", "exported：全链完成", "—")


def _identities(bid):
    """暗标禁标标识清单：取 01c.typography.identity_ban（缺失/解析失败按空清单）。"""
    p = os.path.join(bid, "01c_format-outline.json")
    if not os.path.exists(p):
        return []
    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        return [str(x) for x in (data.get("typography") or {}).get("identity_ban", [])
                if str(x).strip()]
    except (json.JSONDecodeError, OSError):
        return []


def verify_only(bid, meta, rep):
    """核查模式（只读）：一致性 + 只读校验器。返回 (verdict, rc)。"""
    stage = meta.get("stage", "")
    fails = rep["fails"]
    idx = STAGE_ORDER.index(stage) if stage in STAGE_ORDER else -1
    # stage↔产物一致性（stage 已达标 ⇒ 产物必须在）
    for name, gate, rels in IMPLIED:
        if idx >= STAGE_ORDER.index(gate):
            for m in _missing(bid, rels):
                fails.append("一致性 FAIL：stage=%s 已过「%s」，缺 %s" % (stage, name, m))
    # 只读校验器：① 契约（无条件，缺件自 skip）；③ 双检（有章节才跑）
    rc, lines = _sh(_S("bid-response-plan", "validate_plan.py"), bid)
    rep["validators"].append({"name": "① validate_plan（产物契约）", "rc": rc, "tail": _tail(lines)})
    if rc != 0:
        fails.append("validate_plan rc=%d（① 产物契约校验硬失败）" % rc)
    if _chapters(bid):
        for nm, script in (("③ check_facts（事实引用）", "check_facts.py"),
                           ("③ word_count（篇幅）", "word_count.py")):
            rc, lines = _sh(_S("bid-technical-proposal", script), bid)
            rep["validators"].append({"name": nm, "rc": rc, "tail": _tail(lines)})
            if rc == 1:
                fails.append("%s rc=1（正文存在错误项，五步循环步5 前置未清零）" % nm)
            elif rc == 2:
                rep["notes"].append("%s rc=2（前置缺失，信息态——按交接约定不代补）" % nm)
    else:
        rep["validators"].append({"name": "③ check_facts", "rc": None, "tail": "skip（无 05_chapters）"})
        rep["validators"].append({"name": "③ word_count", "rc": None, "tail": "skip（无 05_chapters）"})
    # 暗标套件级标识扫描（bid_mode=blind；04 计划书 §11 阶段 4）：
    # 05_chapters 是交付正文的唯一来源，禁标清单=01c.typography.identity_ban；
    # 命中＝FAIL（内容修改归 ③）；清单空＝信息态提示（回 ⓪/① 补录），不臆造。
    if meta.get("bid_mode") == "blind":
        ident = _identities(bid)
        if not ident:
            rep["notes"].append("暗标模式但 01c.typography.identity_ban 为空（禁标标识清单未录入，回 ⓪/① 补齐）")
        else:
            hits = []
            for f in _expand(bid, "05_chapters/*.md"):
                try:
                    with open(f, encoding="utf-8") as fh:
                        t = fh.read()
                except OSError:
                    continue
                for s in ident:
                    if s in t:
                        hits.append("%s 命中「%s」" % (os.path.basename(f), s))
            rep["identity_scan"] = {"identities": ident, "hits": hits}
            if hits:
                for h in hits:
                    fails.append("暗标标识命中（交付正文）：%s（内容修改归 ③，重导前不得交付）" % h)
            else:
                rep["notes"].append("暗标标识扫描：%d 项清单 × 05_chapters 零命中 ✅" % len(ident))
    return ("FAIL" if fails else "PASS"), (1 if fails else 0)


def run_chain(bid, meta, rep):
    """串联模式：从当前 stage 推进机器可执行段；人工关卡/内容环节停住。
    返回 (verdict, rc)。verdict ∈ PASS/STOP/FAIL/BLOCKED。"""
    fails = rep["fails"]
    steps = rep["steps"]

    def rec(label, rc, lines, note=""):
        steps.append({"step": label, "rc": rc, "tail": _tail(lines), "note": note})
        mark = "OK" if rc == 0 else "!!"
        print("  [%s] rc=%d %s" % (mark, rc, label))
        for ln in lines[-3:]:
            print("        " + ln)
        if note:
            print("        note: " + note)

    def stop(where, help_):
        rep["stopped_at"] = where
        rep["stop_help"] = help_
        return "STOP", 0

    stage0 = meta.get("stage", "")

    # ---- 段 ①：计划产物（机器；入口断言 stage=reviewed）----
    if stage0 == "reviewed":
        if _missing(bid, ["01_tender-facts.json"]):
            fails.append("① 前置缺失：01_tender-facts.json（先跑 ⓪）")
            return "BLOCKED", 2
        rc, lines = _sh(_S("bid-response-plan", "build_bid_plan.py"), bid)
        rec("① build_bid_plan（01c/01b/03c/03/04＋素材缺口清单）", rc, lines)
        if rc != 0:
            fails.append("① build_bid_plan rc=%d" % rc)
            return "FAIL", 1
        miss = _missing(bid, IMPLIED[1][2])
        if miss:
            fails.append("① 产物缺件：%s" % "、".join(miss))
            return "FAIL", 1
    # ---- 关卡 G2/G1（人工；① 出口两关）----
    if stage0 in ("reviewed", "facts_confirmed", "planning"):
        g = "G2＋G1" if stage0 == "reviewed" else "G1"
        return stop("① 关卡 %s（人工）" % g,
                    GATE_HELP["G2"] + "；" + GATE_HELP["G1"] if stage0 == "reviewed" else GATE_HELP["G1"])

    # ---- 段 ②-A：覆盖检查（机器；checking 重跑合法）----
    if stage0 in ("plan_confirmed", "checking"):
        need = ["01_tender-facts.json", "01b_spec-items.json", "01c_format-outline.json",
                "03_bid-plan.json", "04_outline.json", "03c_business-forms.json"]
        miss = _missing(bid, need)
        if miss:
            fails.append("②-A 前置缺件：%s" % "、".join(miss))
            return "BLOCKED", 2
        if not (_expand(bid, "02_facts.md") or _expand(bid, "02_facts.yaml")):
            rep["notes"].append("02_facts 缺失（交接约定：可缺，任务卡 blocked_by_facts，须显式告警）")
        rc, lines = _sh(_S("bid-compliance-check", "check_compliance.py"), bid, ["--mode", "A"])
        rec("②-A check_compliance --mode A（覆盖检查）", rc, lines)
        if rc != 0:
            fails.append("②-A check_compliance rc=%d" % rc)
            return "FAIL", 1
        rc, lines = _sh(_S("bid-compliance-check", "check_business.py"), bid, ["--mode", "A"])
        rec("②-A check_business --mode A（商务表零金额）", rc, lines)
        if rc != 0:
            fails.append("②-A check_business rc=%d" % rc)
            return "FAIL", 1
    if _stage(bid) in ("plan_confirmed", "checking"):
        return stop("② 关卡 G3（人工）", GATE_HELP["G3"])

    # ---- 段 ③：正文（内容环节 + 关卡 G4）----
    stage = _stage(bid)
    if stage == "check_confirmed":
        if not _chapters(bid):
            return stop("③ 写作（内容环节）",
                        "③ 五步循环逐章成稿（LLM 写作，每章动笔前过 G4）；产物=05_chapters/n-xxxx.md")
        return stop("③ 关卡 G4（人工）", GATE_HELP["G4"])
    if stage == "route_confirmed":
        return stop("③ 写作（内容环节·续）",
                    "首章已确认；后续章逐章 G4，全部 final 后写 stage=writing")

    # ---- 段 ②-B：成稿响应检查（机器；写 stage=rechecking）----
    if stage in ("writing", "rechecking"):
        if not _chapters(bid):
            fails.append("②-B 前置：stage=%s 但 05_chapters/ 无成稿（状态与产物不一致）" % stage)
            return "FAIL", 1
        if not _expand(bid, "06_compliance/compliance-report.md"):
            fails.append("②-B 前置：06_compliance/compliance-report.md 缺失（先跑 ②-A）")
            return "BLOCKED", 2
        if not _expand(bid, "08_business/deviation-table.md"):
            return stop("②-B 前置（人工落点）",
                        "08_business/deviation-table.md 缺失——按 ② SKILL §②-B："
                        "首列=01b 条目id（sp-xxx）逐行对齐填写后重跑")
        # ③ 事实引用机检（E1-E4 未清零不得交背对背复核——③ SKILL 五步循环步5 前置）
        rc, lines = _sh(_S("bid-technical-proposal", "check_facts.py"), bid)
        rec("②-B 前置 ③ check_facts（事实引用清零核验）", rc, lines)
        if rc == 1:
            fails.append("③ check_facts rc=1（E1-E4 未清零，须回 ③ 五步循环修正）")
            return "FAIL", 1
        if rc == 0:
            rc2, lines2 = _sh(_S("bid-technical-proposal", "word_count.py"), bid)
            rec("③ word_count（篇幅对照，信息态）", rc2, lines2)
        rc, lines = _sh(_S("bid-compliance-check", "check_compliance.py"), bid, ["--mode", "B"])
        rec("②-B check_compliance --mode B（成稿响应；写 stage=rechecking）", rc, lines,
            "rc=1＝检出未响应/跨章不一致（G5 处置材料，非驱动器失败）" if rc == 1 else "")
        if rc == 2:
            fails.append("②-B check_compliance rc=2（前置阻断）")
            return "BLOCKED", 2
        rc, lines = _sh(_S("bid-compliance-check", "check_consistency.py"), bid)
        rec("②-B check_consistency（跨章一致性）", rc, lines,
            "rc=1＝检出 ⚠️ 不一致（G5 处置材料，非驱动器失败）" if rc == 1 else "")
        if rc == 2:
            fails.append("②-B check_consistency rc=2（前置阻断）")
            return "BLOCKED", 2
    if _stage(bid) in ("writing", "rechecking"):
        return stop("② 关卡 G5（人工）", GATE_HELP["G5"])

    # ---- 段 ④：导出链（机器；七脚本按序，rc 非 0 即停）----
    stage = _stage(bid)
    if stage == "recheck_confirmed":
        # 暗标联动：把 01c.identity_ban 传给 verify_docx（docx/pdf/页眉页脚级扫描），
        # 驾驶员不臆造标识，清单空则提示（正文级扫描见 verify 模式）。
        ident = []
        if meta.get("bid_mode") == "blind":
            ident = _identities(bid)
            if not ident:
                rep["notes"].append("暗标模式但 identity_ban 为空：④ verify_docx 将跳过标识扫描（回 ⓪/① 补录）")
        for script, label, failnote in EXPORT_CHAIN:
            extra = ["--identity", ",".join(ident)] if (script == "verify_docx.py" and ident) else ()
            rc, lines = _sh(_S("bid-docx-export", script), bid, extra)
            rec(label, rc, lines)
            if rc != 0:
                fails.append("%s rc=%d：%s" % (label, rc, failnote))
                return "FAIL", 1
        stage = _stage(bid)
        if stage != "exported":
            fails.append("④ 链跑完但 stage=%r（verify_docx 未写回 exported）" % stage)
            return "FAIL", 1
    if stage0 == "exhausted":
        return stop("exhausted", "回退重试耗尽（≤2 轮），人工处置后重置 stage")
    return "PASS", 0


def print_report(bid, rep):
    print("---- 产物清点 ----")
    for gname, rels in INVENTORY_GROUPS:
        cells = []
        for r in rels:
            hits = _expand(bid, r)
            if "*" in r:
                cells.append("%s×%d" % (r, len(hits)))
            else:
                cells.append("%s%s" % (r, "✓" if hits else "✗"))
        print("[%s] %s" % (gname, "  ".join(cells)))
    if rep["validators"]:
        print("---- 校验器（只读） ----")
        for v in rep["validators"]:
            print("  %-28s rc=%-4s %s" % (v["name"], v["rc"], v["tail"]))
    if rep["notes"]:
        print("---- 提示（信息态） ----")
        for n in rep["notes"]:
            print("  ℹ️ " + n)
    if rep.get("stopped_at"):
        print("---- 串联停点 ----")
        print("  停在：%s" % rep["stopped_at"])
        print("  处置：%s" % rep.get("stop_help", ""))
    fr = rep.get("frontier") or {}
    print("---- 可达边界（frontier） ----")
    print("  段：%s ｜ 原因：%s" % (fr.get("segment"), fr.get("reason")))
    print("  下一步：%s" % fr.get("next"))
    if rep["fails"]:
        print("---- FAIL 明细 ----")
        for f_ in rep["fails"]:
            print("  ❌ " + f_)


def main():
    ap = argparse.ArgumentParser(description="五技能链端到端阶段验收驱动器（阶段 4）")
    ap.add_argument("--bid", required=True, help="项目 bid 目录")
    ap.add_argument("--run", action="store_true",
                    help="串联模式：推进机检链（会改写产物与 stage；仅用于 acceptance 副本）")
    ap.add_argument("--json", dest="json_out", default=None, help="机器可读报告输出路径")
    args = ap.parse_args()
    bid = os.path.abspath(args.bid)
    if not os.path.isdir(bid):
        print("FAIL bid 目录不存在：%s" % bid)
        return 2
    if not os.path.exists(os.path.join(bid, "00_metadata.json")):
        print("【结构性阻断】00_metadata.json 不存在（流水线未初始化——先执行 ⓪ 招标解读）")
        return 2
    meta = _load_meta(bid)
    stage0 = meta.get("stage", "")
    rep = {
        "schema_version": "0.1",
        "mode": "run" if args.run else "verify",
        "bid": bid,
        "stage_start": stage0,
        "bid_mode": meta.get("bid_mode"),
        "style_source": meta.get("style_source"),
        "skill_versions": meta.get("skill_versions", {}),
        "fails": [], "notes": [], "validators": [], "steps": [],
        "stopped_at": None, "stop_help": None,
    }
    print("=" * 72)
    print("run_acceptance ｜ 模式=%s ｜ bid=%s" % (rep["mode"], bid))
    print("stage=%s（%s）｜ bid_mode=%s ｜ style_source=%s"
          % (stage0, STAGE_LABEL.get(stage0, "?"), meta.get("bid_mode"), meta.get("style_source")))
    print("=" * 72)
    if args.run:
        print("⚠️  串联模式会改写产物与 00_metadata.stage——仅用于 workdir/acceptance 副本")
        verdict, rc = run_chain(bid, meta, rep)
    else:
        verdict, rc = verify_only(bid, meta, rep)
    stage_end = _stage(bid)
    rep["stage_end"] = stage_end
    seg, why, nxt = frontier_of(bid, stage_end)
    rep["frontier"] = {"segment": seg, "reason": why, "next": nxt}
    rep["verdict"] = verdict
    rep["rc"] = rc
    rep["generated_at"] = _dt.datetime.now().astimezone().replace(microsecond=0).isoformat()
    print()
    print_report(bid, rep)
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(rep, f, ensure_ascii=False, indent=1)
        print("JSON 报告 →", args.json_out)
    print("-" * 72)
    print("结论：%s（rc=%d）" % (verdict, rc))
    return rc


if __name__ == "__main__":
    sys.exit(main())
