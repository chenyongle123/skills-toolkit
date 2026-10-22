#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/test_stage4_regression.py — 阶段 4（端到端串联）永久回归

覆盖：
  T4-1 全链 E2E 正向（合成 mini 项目，经 tests/run_acceptance.py --run 逐段推进）：
     ① build_bid_plan（示例市口径硬编码产物落合成库）→ 人工 G2+G1 → ②-A 双脚本 →
     人工 G3 → ③ 42 章成稿＋02_facts（模拟 LLM 写作）→ 人工 G4/route→writing →
     ②-B 人工偏离表（由真 01b 1266 条机械生成）→ ②-B 双脚本（写 stage=rechecking）→
     人工 G5 → ④ 七脚本 → stage=exported＋skill_versions 登记；终态 verify PASS。
  T4-2 逐段停点：每段 STOP 在正确的人工关卡/内容环节，处置指引可读（并入 T4-1 断言）。
  T4-3 跳步负例：① 在 plan_confirmed 被拒（assert reviewed）；②-B 在 check_confirmed
     rc=2；④ export_docx 在 writing rc=2 且零产物。
  T4-4 状态-产物不一致：stage=plan_confirmed 缺 01b → verify FAIL rc=1；
     stage=writing 无章节 → --run FAIL（不代补）。
  T4-5 frontier 六态矩阵：reviewed→G2／plan_confirmed→G3／check_confirmed→③ 写作／
     rechecking→G5／recheck_confirmed→④ 导出链／exported→链路终点。
  T4-6 --json 报告结构（mode/stage_start/stage_end/frontier/validators/verdict/rc）。
  T4-7 暗标套件级标识扫描（run_acceptance verify 模式）：bid_mode=blind ×
     01c.identity_ban 命中 05_chapters → FAIL；清单空 → 信息态提示不误伤。

用法：python tests/test_stage4_regression.py（退出码 0=全过，1=有失败）
依赖：零三方依赖。人工关卡由测试直写 00_metadata.stage 模拟（交接约定 §六：
G1–G5 只能人工确认，驱动器与脚本均不代写——本测试即"人"）。
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RA = ROOT / "tests" / "run_acceptance.py"
BP = ROOT / "skills" / "bid-response-plan" / "scripts" / "build_bid_plan.py"
CC = ROOT / "skills" / "bid-compliance-check" / "scripts" / "check_compliance.py"
ED = ROOT / "skills" / "bid-docx-export" / "scripts" / "export_docx.py"

results = []
TMP_BIDS = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print("%s  %s%s" % ("PASS" if ok else "FAIL", name, ("　— " + detail) if detail and not ok else ""))


def run_py(script, *args):
    env = dict(os.environ, PYTHONUTF8="1")
    return subprocess.run([sys.executable, str(script), *args],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", env=env)


def ra(bid, *extra):
    return run_py(RA, "--bid", str(bid), *extra)


def w(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def wj(path, obj):
    w(path, json.dumps(obj, ensure_ascii=False, indent=1))


def read_meta(bid):
    return json.loads((Path(bid) / "00_metadata.json").read_text(encoding="utf-8"))


def human_confirm(bid, stage):
    """模拟人工关卡确认（交接约定 §六：G1–G5 由人写 stage，AI 不代写）。"""
    p = Path(bid) / "00_metadata.json"
    m = read_meta(bid)
    m["stage"] = stage
    m["updated_at"] = "2026-10-22T10:00:00+08:00"
    p.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")


def make_pdf(pages: int) -> bytes:
    """手写经典 xref 的 N 页空白 PDF（零依赖造件，与 T3 同款）。"""
    kids = b" ".join(b"%d 0 R" % (3 + i) for i in range(pages))
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [" + kids + b"] /Count %d >>" % pages]
    for _ in range(pages):
        objs.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << >> >>")
    out = bytearray(b"%PDF-1.4\n")
    offs = [0]
    for i, bd in enumerate(objs, 1):
        offs.append(len(out))
        out += b"%d 0 obj\n" % i + bd + b"\nendobj\n"
    x = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for i in range(1, len(objs) + 1):
        out += b"%010d 00000 n \n" % offs[i]
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, x)
    return bytes(out)


# ---------- 合成 mini 项目 ----------

FACT_POOL = ["qual-001", "perf-001", "pers-001", "eq-001", "fin-2022"]

# 证据扫描件命名（④ index_evidence fact_ref 匹配＝文件名与 scan 卡 notes+id 共享
# ≥4 字连续子串、首中即停）：逐卡选唯一关键词，20 张 scan 卡全覆盖（check_evidence
# 五项检查之「缺件」零错误的前置）。A-17 用卡尾号 0028——bf-07 的审计报告/资信证明
# 二词均被更早的 t-0004（三年审计报告+银行资信证明）占用，id 前缀 t-002 又与
# t-0023/24/25 撞，唯一安全子串是尾号 0028。
EVIDENCE_FILES = [
    ("A-01_施工总承包一级", 2), ("A-02_分工比例", 1), ("A-03_风电EPC业绩", 2),
    ("A-04_三年审计报告", 3), ("A-05_一级建造师", 2), ("A-06_信用查询截图", 4),
    ("A-07_管理机构", 1), ("A-08_重大诉讼", 2), ("A-09_保函原件", 1),
    ("A-10_初步评审", 1), ("A-11_无法解密", 1), ("A-12_分开装订", 1),
    ("A-13_投标文件加密", 2), ("A-14_原件随投标", 1), ("A-15_法人身份证", 2),
    ("A-16_有效委托书", 1), ("A-17_0028", 1), ("A-18_设备制造商", 1),
    ("A-19_完工业绩表", 3), ("A-20_新承接业绩", 2),
]


def mk_synth():
    """合成 ⓪ 出口态 bid：00_metadata(stage=reviewed) + 01_tender-facts（契约 0.4）。

    clauses 覆盖 ① 硬编码任务卡引用的 c-0008..c-0025/c-0059..061（②/③ 类），
    scoring 限 S-01/02/03（与 ① TASKS 对齐 → coverage.unmapped=[]）。
    """
    bid = Path(tempfile.mkdtemp(prefix="t4reg_"))
    TMP_BIDS.append(bid)
    wj(bid / "00_metadata.json", {
        "schema_version": "0.1", "stage": "reviewed",
        "project": {"name": "合成端到端测试项目EPC总承包", "no": "T4-2026-001",
                    "purchaser": "合成测试业主"},
        "bid_mode": "normal", "style_source": "tender_required",
        "deadline": "2027-06-01T10:00+08:00",
        "failed_nodes": [], "warnings": [],
    })
    qual = {"c-0008", "c-0009", "c-0010", "c-0011", "c-0012", "c-0013", "c-0014"}
    clauses = []
    for i in range(8, 26):
        cid = "c-%04d" % i
        clauses.append({"id": cid,
                        "category": "②投标资格条件" if cid in qual else "③废标/否决情形",
                        "item": "条款事项" + cid,
                        "consequence": "不满足即否决" if cid not in qual else "资格后审项"})
    for cid in ("c-0059", "c-0060", "c-0061"):
        clauses.append({"id": cid, "category": "②投标资格条件", "item": "条款事项" + cid,
                        "consequence": "资格后审项"})
    wj(bid / "01_tender-facts.json", {
        "contract_schema_version": "0.4",
        "clauses": clauses,
        "scoring": {"items": [{"id": "S-01"}, {"id": "S-02"}, {"id": "S-03"}]},
    })
    return bid


def write_facts_and_chapters(bid):
    """模拟 ③ 写作：02_facts.md（G2 事实库）＋ 01c 全章节 n-xxxx.md 成稿。

    每段带 [[F:]]/[[S:]] 来源标注（过 check_facts E3）；frontmatter 按
    chapter.schema.json 0.1 全字段。返回章节数。
    """
    w(bid / "02_facts.md",
      "# 投标人事实库（合成）\n\n" +
      "\n".join("- {id: %s, name: 合成事实, source: 事实库}" % f for f in FACT_POOL) + "\n")
    outline = json.loads((Path(bid) / "01c_format-outline.json").read_text(encoding="utf-8"))
    chs = outline["chapters"]
    for i, node in enumerate(chs):
        cid, num, title = node["id"], str(node.get("number", "")), node["title"]
        f1 = FACT_POOL[i % len(FACT_POOL)]
        f2 = FACT_POOL[(i + 1) % len(FACT_POOL)]
        fm = ("---\nschema_version: 0.1\nchapter_id: %s\nnumber: \"%s\"\ntitle: %s\n"
              "status: final\nword_target: 100\ng4:\n  confirmed: true\n"
              "  confirmed_by: 合成测试\n  confirmed_at: 2026-10-22\n"
              "  route_summary:\n    - 合成路线要点一\n    - 合成路线要点二\n---\n\n"
              % (cid, num, title))
        body = ("本章内容依据已核事实[[F:%s]]编制，组织机构与职责分工明确，"
                "关键安排均有事实来源支撑。\n\n"
                "资源配置与选型说明引事实库[[F:%s]]，不含无来源推演结论，"
                "评分点响应对齐评分办法[[S:S-0%d]]。\n" % (f1, f2, i % 3 + 1))
        w(Path(bid) / "05_chapters" / ("%s.md" % cid), fm + body)
    return len(chs)


def write_dev_table(bid):
    """模拟 ②-B 人工偏离表：由真 01b 逐条机械生成（响应值=要求值去限定符）。

    返回行数。跳条/多行/重行/照抄/断链全零——B 类干净闭环（G5 材料）。
    """
    outline = json.loads((Path(bid) / "01c_format-outline.json").read_text(encoding="utf-8"))
    ch_ids = [c["id"] for c in outline["chapters"]]
    items = json.loads((Path(bid) / "01b_spec-items.json").read_text(encoding="utf-8"))["items"]
    head = ("| 条目id | 条款号 | 要求项 | 招标要求值 | 单位 | 响应值 | 偏离判定 | 不允许负偏离 | 出处 |\n"
            "|---|---|---|---|---|---|---|---|---|\n")
    lines = []
    qual_re = re.compile(r"[≥≤＞＜<>]|不低于|不高于|不超过|不少于|至少|最多|以上|以下")
    for i, it in enumerate(items):
        req = str(it.get("required_value") or "")
        resp = qual_re.sub("", req).strip() or "满足"
        src = "%s 第1段" % ch_ids[i % len(ch_ids)]
        no_neg = "true" if it.get("no_negative_allowed") else "false"
        lines.append("| %s | %s | %s | %s | %s | %s | 无偏离 | %s | %s |"
                     % (it["id"], it.get("clause", ""), it.get("requirement", ""),
                        req, it.get("unit", ""), resp, no_neg, src))
    w(Path(bid) / "08_business" / "deviation-table.md",
      "# 响应偏离表（人工填写）\n\n" + head + "\n".join(lines) + "\n")
    return len(lines)


# ---------- T4-1/T4-2 全链 E2E 正向（含逐段停点断言） ----------

def t4_1():
    bid = mk_synth()
    # --- 段 ①：⓪ 出口态 → 计划产物 ---
    r = ra(bid, "--run")
    out = r.stdout
    check("T4-1a ① 段推进 rc=0", r.returncode == 0, "rc=%s %s" % (r.returncode, out[-300:]))
    check("T4-1b ① 产物五件落盘",
          all((bid / n).exists() for n in
              ("01b_spec-items.json", "01c_format-outline.json", "03_bid-plan.json",
               "03c_business-forms.json", "04_outline.json")))
    check("T4-1c 停在 ① 关卡 G2＋G1（人工）", "G2＋G1" in out and "STOP" in out, out[-300:])
    plan = json.loads((bid / "03_bid-plan.json").read_text(encoding="utf-8"))
    check("T4-1d coverage.unmapped 空（G1 前置）", plan.get("coverage", {}).get("unmapped") == [],
          str(plan.get("coverage", {}))[:200])
    # --- 人工 G2+G1 → plan_confirmed ---
    human_confirm(bid, "plan_confirmed")
    r = ra(bid, "--run")
    out = r.stdout
    check("T4-1e ②-A 段推进 rc=0（双脚本）",
          r.returncode == 0 and "check_compliance --mode A" in out and "check_business" in out,
          "rc=%s %s" % (r.returncode, out[-300:]))
    check("T4-1f ②-A 产物四件落盘",
          all((bid / "06_compliance" / n).exists() for n in
              ("compliance-report.md", "compliance-report.json", "form-check.md",
               "business-check.md")))
    check("T4-1g 停在 ② 关卡 G3（人工）", "G3" in out, out[-300:])
    rep = json.loads((bid / "06_compliance" / "compliance-report.json").read_text(encoding="utf-8"))
    check("T4-1h ②-A entry_ok（plan_confirmed 合法入口）",
          rep.get("summary", {}).get("entry_ok") is True)
    # --- 人工 G3 → check_confirmed ---
    human_confirm(bid, "check_confirmed")
    r = ra(bid, "--run")
    out = r.stdout
    check("T4-1i 停在 ③ 写作（内容环节，无成稿）",
          r.returncode == 0 and "③ 写作" in out and "05_chapters" in out, out[-300:])
    # --- 模拟 ③ 写作：42 章＋02_facts ---
    n_ch = write_facts_and_chapters(bid)
    check("T4-1j 01c 全量章节成稿（42 章）", n_ch == 42, "n_ch=%s" % n_ch)
    r = ra(bid, "--run")
    out = r.stdout
    check("T4-1k 停在 ③ 关卡 G4（首章路线待确认）",
          r.returncode == 0 and "G4" in out, out[-300:])
    # --- 人工 G4 → route_confirmed；再 writing ---
    human_confirm(bid, "route_confirmed")
    r = ra(bid, "--run")
    out = r.stdout
    check("T4-1l route_confirmed 停在 ③ 写作·续",
          r.returncode == 0 and "后续章" in out, out[-300:])
    human_confirm(bid, "writing")
    r = ra(bid, "--run")
    out = r.stdout
    check("T4-1m writing 停在 ②-B 人工落点（偏离表缺失）",
          r.returncode == 0 and "deviation-table" in out and "人工落点" in out, out[-300:])
    # --- 模拟人工偏离表（真 01b 逐条）→ ②-B 双脚本 ---
    n_rows = write_dev_table(bid)
    check("T4-1n 偏离表与 01b 同条数（1266）", n_rows == 1266, "n_rows=%s" % n_rows)
    r = ra(bid, "--run")
    out = r.stdout
    check("T4-1o ②-B 段推进 rc=0（check_facts＋mode B＋consistency）",
          r.returncode == 0 and "check_facts" in out and "--mode B" in out
          and "check_consistency" in out,
          "rc=%s %s" % (r.returncode, out[-400:]))
    m = read_meta(bid)
    check("T4-1p ②-B 写回 stage=rechecking", m.get("stage") == "rechecking",
          "stage=%s" % m.get("stage"))
    check("T4-1q consistency-issues.md 落盘",
          (bid / "06_compliance" / "consistency-issues.md").exists())
    check("T4-1r 停在 ② 关卡 G5（人工）", "G5" in out, out[-300:])
    dt = (bid / "06_compliance" / "deviation-table.md").read_text(encoding="utf-8")
    check("T4-1s ②-B 偏离表结论干净（跳条 0 且零错误项）",
          "跳条 0" in dt and "❌" not in dt, dt[-400:])
    # --- 人工 G5 → recheck_confirmed；放证据扫描件 → ④ 七脚本 ---
    human_confirm(bid, "recheck_confirmed")
    ev = bid / "evidence"
    ev.mkdir(parents=True, exist_ok=True)
    for name, pages in EVIDENCE_FILES:
        (ev / ("%s.pdf" % name)).write_bytes(make_pdf(pages))
    r = ra(bid, "--run")
    out = r.stdout
    check("T4-1t ④ 段推进 rc=0（七脚本全过）",
          r.returncode == 0 and "④.7 verify_docx" in out and "exported" in out,
          "rc=%s %s" % (r.returncode, out[-400:]))
    m = read_meta(bid)
    check("T4-1u ④ 写回 stage=exported", m.get("stage") == "exported",
          "stage=%s" % m.get("stage"))
    check("T4-1v skill_versions 登记 bid-docx-export=0.2.2",
          m.get("skill_versions", {}).get("bid-docx-export") == "0.2.2",
          str(m.get("skill_versions")))
    check("T4-1w ④ 产物五件落盘",
          all((bid / "07_out" / n).exists() for n in
              ("style-profile.yaml", "投标文件.docx", "投标文件_含附件.pdf",
               "pagination.json", "verify-report.md"))
          and (bid / "03b_evidence-index.json").exists())
    with zipfile.ZipFile(bid / "07_out" / "投标文件.docx") as z:
        names = z.namelist()
    check("T4-1x docx 包完整（document＋styles）",
          "word/document.xml" in names and any("styles" in n for n in names))
    # --- 终态：核查模式全绿 ---
    r = ra(bid)
    check("T4-1y 终态 verify 模式 PASS rc=0",
          r.returncode == 0 and "结论：PASS" in r.stdout,
          "rc=%s %s" % (r.returncode, r.stdout[-400:]))


# ---------- T4-3 跳步负例 ----------

def t4_3():
    bid = mk_synth()
    human_confirm(bid, "plan_confirmed")  # 越级：未跑 ①
    r = run_py(BP, "--bid", str(bid))
    check("T4-3a ① build_bid_plan 在 plan_confirmed 被拒（assert reviewed）",
          r.returncode != 0 and "reviewed" in (r.stdout + r.stderr),
          "rc=%s" % r.returncode)
    bid = mk_synth()
    human_confirm(bid, "check_confirmed")  # 越级：直跑 ②-B
    r = run_py(CC, "--bid", str(bid), "--mode", "B")
    check("T4-3b ②-B 在 check_confirmed 拒绝 rc=2",
          r.returncode == 2, "rc=%s %s" % (r.returncode, r.stdout[-200:]))
    bid = mk_synth()
    human_confirm(bid, "writing")  # 越级：直跑 ④
    r = run_py(ED, "--bid", str(bid))
    check("T4-3c ④ export_docx 在 writing 拒绝 rc=2",
          r.returncode == 2 and "recheck_confirmed" in r.stdout,
          "rc=%s %s" % (r.returncode, r.stdout[-200:]))
    check("T4-3d 越级零产物", not (bid / "07_out" / "投标文件.docx").exists())


# ---------- T4-4 状态-产物不一致检出 ----------

def t4_4():
    bid = mk_synth()
    human_confirm(bid, "plan_confirmed")  # 声称已过 G1，但 ① 未跑（01b 缺）
    r = ra(bid)
    check("T4-4a verify 检出 stage↔产物不一致 rc=1",
          r.returncode == 1 and "01b_spec-items.json" in r.stdout and "一致性 FAIL" in r.stdout,
          "rc=%s %s" % (r.returncode, r.stdout[-300:]))
    bid = mk_synth()
    human_confirm(bid, "writing")  # 越级 writing 且无成稿
    r = ra(bid, "--run")
    check("T4-4b --run 对 writing 无成稿判 FAIL（不代补）",
          r.returncode == 1 and "不一致" in r.stdout,
          "rc=%s %s" % (r.returncode, r.stdout[-300:]))


# ---------- T4-5 frontier 六态矩阵 ----------

def t4_5():
    # segment 取 run_acceptance.frontier_of 的真实段名（verify 模式打印「段：…」行）
    matrix = [
        ("reviewed", "① 关卡 G2＋G1"), ("plan_confirmed", "② 关卡 G3"),
        ("check_confirmed", "③ 写作"), ("rechecking", "② 关卡 G5"),
        ("recheck_confirmed", "④ 导出链"), ("exported", "链路终点"),
    ]
    for i, (stage, seg) in enumerate(matrix):
        bid = mk_synth()
        human_confirm(bid, stage)
        r = ra(bid)
        check("T4-5%s frontier(%s)=%s" % ("abcdef"[i], stage, seg),
              ("段：%s" % seg) in r.stdout, r.stdout[-200:])


# ---------- T4-6 --json 报告结构 ----------

def t4_6():
    bid = mk_synth()
    jp = Path(tempfile.mkdtemp(prefix="t4json_")) / "rep.json"
    r = ra(bid, "--json", str(jp))
    ok = r.returncode == 0 and jp.exists()
    check("T4-6a --json 落盘且 rc=0", ok, "rc=%s" % r.returncode)
    if ok:
        d = json.loads(jp.read_text(encoding="utf-8"))
        check("T4-6b 结构键齐（mode/stage_start/stage_end/frontier/validators/verdict）",
              all(k in d for k in ("mode", "stage_start", "stage_end", "frontier",
                                   "validators", "verdict", "rc", "fails")))
        check("T4-6c mode=verify 且 stage_start=reviewed",
              d["mode"] == "verify" and d["stage_start"] == "reviewed")
        check("T4-6d frontier 为 dict（segment/reason/next）",
              isinstance(d["frontier"], dict)
              and {"segment", "reason", "next"} <= set(d["frontier"]))
        check("T4-6e verdict=PASS 且 fails 空", d["verdict"] == "PASS" and d["fails"] == [])


# ---------- T4-7 暗标套件级标识扫描（verify 模式） ----------

def _patch_json(path, fn):
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    fn(d)
    Path(path).write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def t4_7():
    bid = mk_synth()
    _patch_json(bid / "00_metadata.json", lambda m: m.update(bid_mode="blind"))
    ra(bid, "--run")                     # ① 产物（停在 G2+G1）
    human_confirm(bid, "plan_confirmed")
    ra(bid, "--run")                     # ②-A 产物（停在 G3）
    human_confirm(bid, "check_confirmed")
    write_facts_and_chapters(bid)
    # 注入禁标标识（段落带 [[F:]]，不触发 check_facts E3）
    ch0 = bid / "05_chapters" / "n-1001.md"
    ch0.write_text(ch0.read_text(encoding="utf-8")
                   + "\n本方案由合成建设集团[[F:qual-001]]编制。\n", encoding="utf-8")
    _patch_json(bid / "01c_format-outline.json",
                lambda d: d.setdefault("typography", {}).update(identity_ban=["合成建设集团"]))
    r = ra(bid)
    check("T4-7a 暗标标识命中 05_chapters → verify FAIL rc=1",
          r.returncode == 1 and "暗标标识命中" in r.stdout and "合成建设集团" in r.stdout,
          "rc=%s %s" % (r.returncode, r.stdout[-300:]))
    # 负例：清单空 → 信息态提示、不误伤（正文仍有该串但无清单即不扫）
    _patch_json(bid / "01c_format-outline.json",
                lambda d: d.setdefault("typography", {}).update(identity_ban=[]))
    r = ra(bid)
    check("T4-7b identity_ban 空 → 提示补录且不误伤 rc=0",
          r.returncode == 0 and "identity_ban 为空" in r.stdout,
          "rc=%s %s" % (r.returncode, r.stdout[-300:]))


def main():
    try:
        for fn in (t4_1, t4_3, t4_4, t4_5, t4_6, t4_7):
            print("\n== %s ==" % fn.__name__)
            fn()
    finally:
        for b in TMP_BIDS:
            shutil.rmtree(b, ignore_errors=True)
    failed = [r for r in results if not r[1]]
    print()
    print("阶段 4 回归（T4-1~T4-7）：共 %d 项，通过 %d，失败 %d"
          % (len(results), len(results) - len(failed), len(failed)))
    if failed:
        print("\n失败明细：")
        for name, _, detail in failed:
            print("  FAIL %s　— %s" % (name, detail))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
