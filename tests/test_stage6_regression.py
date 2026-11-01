#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/test_stage6_regression.py — 阶段 6（素材母库＋企业事实母库）永久回归

覆盖（repo/v1.7.33）：
  T6-1 select_facts.py 快照正向：合成合法母库 → --ids 抽条 → 02_facts.yaml
     在位、节构/schema_version/条目/id 逐字拷贝、无 evidence_ref 字段行、双复核位注释。
  T6-2 快照回读保真：PyYAML 可用时深检（标量类型/is_decisive=False/额外字段保留）；
     不可用时降级文本面断言（记 W 不 FAIL——与 ② _mini_yaml_load 兜底同哲学）。
  T6-3 未知 id → rc=1 且不产出文件（只报告差异、不自动补猜）。
  T6-4 覆盖保护：无 --force 拒绝；--force 先备份再重写，重写内容与选择集一致。
  T6-5 --all 全量快照（含未知字段原样保留）。
  T6-6 check_facts_library.py：合成空库 PASS；目录缺失 rc=2。
  T6-7 check_facts_library.py 负例自证：缺必填/坏日期/id 形态与前缀/重复 id/
     禁录 is_decisive/顶层标量/非本文件节键/amount 非数值/未知文件 → rc=1 全命中。

用法：python tests/test_stage6_regression.py（退出码 0=全过，1=有失败）
依赖：零三方依赖（PyYAML 可选，仅影响 T6-2 断言深度）。
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEL = ROOT / "tools" / "select_facts.py"
CHK = ROOT / "tests" / "check_facts_library.py"

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print("%s  %s%s" % ("PASS" if ok else "FAIL", name,
                        ("　— " + detail) if detail and not ok else ""))


def run_py(script, args):
    p = subprocess.run([sys.executable, str(script)] + args,
                       capture_output=True, text=True, encoding="utf-8")
    return p.returncode, p.stdout + p.stderr


QUAL = """\
qualifications:
  - id: qual-001
    name: 电力工程施工总承包壹级
    cert_no: "DlSAMPLE0001"
    issuer: 样例省住房和城乡建设厅
    valid_to: "2027-06-10"
    source: 证书原件
    updated_at: "2026-10-21"
    owner: 张工
    note: 额外字段原样保留
  - id: qual-002
    name: 安全生产许可证
    cert_no: "SAMPLE-AQ-0002"
    issuer: 样例省住房和城乡建设厅
    valid_to: "2027-10-15"
    source: 证书原件
    updated_at: "2026-10-21"
    owner: 张工
"""

PERF = """\
performances:
  - id: perf-001
    project: 样例风电场100MW EPC
    amount: 45000
    unit: 万元
    contract_no: "SAMPLE-HT-2024-001"
    completed_on: "2024-12-30"
    source: 合同原件
    updated_at: "2026-10-21"
    owner: 张工
"""

EMPTY_SECTIONS = {
    "personnel.yaml": "personnel: []\n",
    "equipment.yaml": "equipment: []\n",
    "financials.yaml": "financials: []\n",
}


def build_lib(base: Path, qual=QUAL, perf=PERF, extra=None):
    lib = base / "lib"
    lib.mkdir(parents=True)
    (lib / "README.md").write_text("# 母库\n", encoding="utf-8")
    (lib / "模板.md").write_text("# 模板\n", encoding="utf-8")
    (lib / "qualifications.yaml").write_text(qual, encoding="utf-8")
    (lib / "performances.yaml").write_text(perf, encoding="utf-8")
    for name, text in EMPTY_SECTIONS.items():
        (lib / name).write_text(text, encoding="utf-8")
    if extra:
        (lib / extra).write_text("rogue\n", encoding="utf-8")
    return lib


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="s6reg_"))
    try:
        lib = build_lib(tmp)
        bid = tmp / "bid"

        # ---------- T6-1 快照正向 ----------
        rc, out = run_py(SEL, ["--library", str(lib), "--bid", str(bid),
                               "--ids", "qual-001,perf-001"])
        snap = bid / "02_facts.yaml"
        text = snap.read_text(encoding="utf-8") if snap.is_file() else ""
        check("T6-1 快照 rc=0 且文件在位", rc == 0 and snap.is_file(), "rc=%s" % rc)
        check("T6-1 schema_version＋双复核位注释",
              'schema_version: "0.1"' in text and "复核位①" in text and "复核位②" in text)
        check("T6-1 选中条目逐字拷贝（id/cert_no/合同号引号形态）",
              "qual-001" in text and "DlSAMPLE0001" in text
              and '"SAMPLE-HT-2024-001"' in text and "qual-002" not in text)
        check("T6-1 无 evidence_ref 字段行（项目语境字段不进快照）",
              "evidence_ref:" not in text)
        check("T6-1 is_decisive 注入 ×2", text.count("is_decisive: false") == 2)

        # ---------- T6-2 回读保真 ----------
        try:
            import yaml  # noqa: F401
            has_yaml = True
        except ImportError:
            has_yaml = False
        if has_yaml and snap.is_file():
            import yaml
            data = yaml.safe_load(text)
            q = data["qualifications"][0]
            p = data["performances"][0]
            check("T6-2 回读：类型/值保真",
                  q["id"] == "qual-001" and q["valid_to"] == "2027-06-10"
                  and q["is_decisive"] is False and "evidence_ref" not in q
                  and q.get("note") == "额外字段原样保留"
                  and p["amount"] == 45000 and p["is_decisive"] is False)
        else:
            check("T6-2 回读降级为文本面（PyYAML 缺失）",
                  "DlSAMPLE0001" in text and "is_decisive: false" in text)

        # ---------- T6-3 未知 id ----------
        bid2 = tmp / "bid2"
        rc, out = run_py(SEL, ["--library", str(lib), "--bid", str(bid2),
                               "--ids", "qual-999"])
        check("T6-3 未知 id → rc=1 且不产出",
              rc == 1 and "qual-999" in out and not (bid2 / "02_facts.yaml").exists())

        # ---------- T6-4 覆盖保护 ----------
        rc, out = run_py(SEL, ["--library", str(lib), "--bid", str(bid),
                               "--ids", "qual-001"])
        check("T6-4 已存在快照拒绝覆盖（提示 --force）", rc == 1 and "--force" in out)
        rc, out = run_py(SEL, ["--library", str(lib), "--bid", str(bid),
                               "--ids", "qual-001", "--force"])
        baks = list(bid.glob("02_facts.yaml.bak-*"))
        text2 = snap.read_text(encoding="utf-8") if snap.is_file() else ""
        check("T6-4 --force 先备份再重写（内容=新选择集）",
              rc == 0 and len(baks) == 1 and "perf-001" not in text2
              and text2.count("is_decisive: false") == 1)

        # ---------- T6-5 全量 ----------
        rc, out = run_py(SEL, ["--library", str(lib), "--bid", str(bid2), "--all"])
        text3 = (bid2 / "02_facts.yaml").read_text(encoding="utf-8")
        check("T6-5 --all 全量 3 条＋额外字段保留",
              rc == 0 and text3.count("is_decisive: false") == 3
              and "额外字段原样保留" in text3)

        # ---------- T6-6 空库绿＋目录缺失 rc=2 ----------
        rc, out = run_py(CHK, ["--library", str(lib)])
        check("T6-6 合成合法母库 checker PASS", rc == 0, out.strip().splitlines()[-1] if out.strip() else "")
        rc, out = run_py(CHK, ["--library", str(tmp / "nope")])
        check("T6-6 目录缺失 → rc=2", rc == 2)

        # ---------- T6-7 checker 负例自证 ----------
        bad_qual = QUAL.replace(
            "    issuer: 样例省住房和城乡建设厅\n    valid_to: \"2027-10-15\"\n"
            "    source: 证书原件\n    updated_at: \"2026-10-21\"\n    owner: 张工\n",
            "    valid_to: 2027/10/15\n"
            "    source: 证书原件\n    updated_at: \"2024-01-01\"\n    owner: 张工\n"
            "    is_decisive: true\n", 1)
        bad_qual += """  - id: zz-003
    name: 形态非法
    cert_no: "Q003"
    issuer: 样例机关
    valid_to: "2027-06-10"
    source: 证书原件
    updated_at: "2026-10-01"
    owner: 张工
  - id: perf-009
    name: 前缀错文件
    cert_no: "Q009"
    issuer: 样例机关
    valid_to: "2027-06-10"
    source: 证书原件
    updated_at: "2026-10-01"
    owner: 张工
  - id: qual-001
    name: 重复id
    cert_no: "Q004"
    issuer: 样例机关
    valid_to: "2027-06-10"
    source: 证书原件
    updated_at: "2026-10-01"
    owner: 张工
"""
        bad_perf = "note: 顶层标量\n" + PERF.replace("    amount: 45000", "    amount: 约肆亿")
        bad_pers = "personnel:\n  - id: pers-001\n    name: 李工\n    cert: 一级建造师\n    cert_no: \"P001\"\n    valid_to: \"2027-03-15\"\n    updated_at: \"2026-10-01\"\n    owner: 张工\n"
        lib2 = build_lib(tmp / "bad", qual=bad_qual, perf=bad_perf, extra="rogue.txt")
        (lib2 / "personnel.yaml").write_text(bad_pers, encoding="utf-8")
        rc, out = run_py(CHK, ["--library", str(lib2)])
        hits = ["未知文件", "顶层标量键 note", "id 形态非法：zz-003",
                "id 前缀 perf- 与文件节 qualifications 不匹配", "id 重复",
                "缺必填字段 issuer", "缺必填字段 source",
                "母库禁录项目语境字段 is_decisive", "字段 valid_to 非 YYYY-MM-DD",
                "字段 amount 非数值"]
        missing = [h for h in hits if h not in out]
        check("T6-7 负例 10 类全命中 → rc=1", rc == 1 and not missing, "missing=%s" % missing)
        check("T6-7 aging 超 12 个月出 W 级", "W: [L7]" in out and "2024-01-01" in out)

        bad = [n for n, ok, _ in results if not ok]
        print("\n阶段 6 回归：%d 项，失败 %d 项" % (len(results), len(bad)))
        if bad:
            for n in bad:
                print("  FAIL:", n)
        return 0 if not bad else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
