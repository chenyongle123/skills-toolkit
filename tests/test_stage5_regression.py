#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/test_stage5_regression.py — 阶段 5（多平台矩阵＋SKILL.lite.md）永久回归

覆盖：
  T5-1 三份 lite 在位且非空（①②③，计划书 §9 硬性要求；④ L0 无承载意义、⓪ 不
     在要求内，二者若存在同样受 T5-2/T5-3 约束）。
  T5-2 lite 形态契约：无 frontmatter（防平台误加载为独立技能造成路由冲突）＋
     四层降级表（L0/L1/L2/L3）在位。
  T5-3 lite 铁律自包含：IRONLAWS 块与同技能主 SKILL.md 逐字一致（防两处漂移）。
  T5-4 §9 硬性要求：每步末尾【能力依赖：L2】标注 ≥3 处，且每处后紧跟降级指令。
  T5-5 触发边界与拒绝路径：lite 无上游产物时的指路文案在位。
  T5-6 R7 状态快照约定：无文件系统平台的对话内状态卡在位；③ 强制"一章一轮"。
  T5-7 C13 检测器负例自证（临时 skills 树上 import validate_contract 直调
     check_lite()：缺 lite／带 frontmatter／铁律漂移／L2 标注不足／④ 前向兼容
     均被抓出；正例无报错）。
  T5-8 validate_contract 全绿（真实仓库，含 C13；须先 --write-lock 对齐版本）。

用法：python tests/test_stage5_regression.py（退出码 0=全过，1=有失败）
依赖：零三方依赖。
"""
from __future__ import annotations

import re
import subprocess
import sys
import shutil
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"
FIVE = ["tender-document-review", "bid-response-plan", "bid-compliance-check",
        "bid-technical-proposal", "bid-docx-export"]
LITE_REQUIRED = ["bid-response-plan", "bid-compliance-check", "bid-technical-proposal"]
VC = ROOT / "tests" / "validate_contract.py"

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print("%s  %s%s" % ("PASS" if ok else "FAIL", name, ("　— " + detail) if detail and not ok else ""))


def lite_path(skill):
    return SKILLS / skill / "SKILL.lite.md"


def lite_text(skill):
    return lite_path(skill).read_text(encoding="utf-8")


def main() -> int:
    # ---------- T5-1 在位且非空 ----------
    for s in LITE_REQUIRED:
        p = lite_path(s)
        ok = p.exists() and len(lite_text(s).splitlines()) >= 60
        check("T5-1 %s/SKILL.lite.md 在位且 ≥60 行" % s, ok,
              "exists=%s" % p.exists())
    check("T5-1 ④/⓪ 不强制 lite（计划书 §9 仅要求 ①②③）",
          not lite_path("bid-docx-export").exists() and not lite_path("tender-document-review").exists(),
          "若已补建须同步扩 C13 的 LITE_REQUIRED 口径")

    # ---------- T5-2 形态契约 ----------
    for s in LITE_REQUIRED:
        t = lite_text(s)
        no_fm = not t.lstrip().startswith("---")
        layers = all(k in t for k in ("L0", "L1", "L2", "L3")) and "四层降级" in t
        check("T5-2 %s lite 无 frontmatter＋四层降级表在位" % s, no_fm and layers,
              "no_fm=%s layers=%s" % (no_fm, layers))

    # ---------- T5-3 铁律自包含且与主文件逐字一致 ----------
    for s in LITE_REQUIRED:
        m = re.search(r"<!-- IRONLAWS:BEGIN -->(.*?)<!-- IRONLAWS:END -->", lite_text(s), re.S)
        mm = re.search(r"<!-- IRONLAWS:BEGIN -->(.*?)<!-- IRONLAWS:END -->",
                       (SKILLS / s / "SKILL.md").read_text(encoding="utf-8"), re.S)
        check("T5-3 %s lite IRONLAWS 与主 SKILL.md 逐字一致" % s,
              bool(m) and bool(mm) and m.group(1).strip() == mm.group(1).strip())

    # ---------- T5-4 每步【能力依赖：L2】+ 紧跟降级指令 ----------
    for s in LITE_REQUIRED:
        lines = lite_text(s).splitlines()
        marks = [i for i, l in enumerate(lines) if "【能力依赖：L2】" in l]
        enough = len(marks) >= 3
        with_fallback = all(
            any("降级指令" in lines[j] for j in range(i, min(i + 4, len(lines))))
            for i in marks)
        check("T5-4 %s L2 标注 ≥3 处且每处紧跟降级指令" % s, enough and with_fallback,
              "marks=%d" % len(marks))

    # ---------- T5-5 触发边界与拒绝路径 ----------
    expect_refuse = {
        "bid-response-plan": ["tender-document-review", "不自行解析"],
        "bid-compliance-check": ["bid-response-plan", "不自行解析招标文件原文"],
        "bid-technical-proposal": ["没有任务卡", "G4"],
    }
    for s, kws in expect_refuse.items():
        t = lite_text(s)
        check("T5-5 %s lite 拒绝路径在位（%s）" % (s, "／".join(kws)),
              all(k in t for k in kws) and "拒绝" in t)

    # ---------- T5-6 R7 状态快照 + 一章一轮 ----------
    for s in LITE_REQUIRED:
        check("T5-6 %s lite R7 状态快照在位" % s, "状态快照" in lite_text(s))
    check("T5-6 ③ lite 强制一章一轮（不得一次生成整本）",
          "一章一轮" in lite_text("bid-technical-proposal") and "不得一次生成整本" in lite_text("bid-technical-proposal"))
    check("T5-6 ② lite F 类三态口径在位",
          all(k in lite_text("bid-compliance-check") for k in ("fact_missing", "expired", "expiring_soon")))

    # ---------- T5-7 C13 检测器负例自证（临时 skills 树直调 check_lite） ----------
    sys.path.insert(0, str(ROOT / "tests"))
    import validate_contract as vc  # noqa: E402

    tmp = Path(tempfile.mkdtemp(prefix="s5_lite_"))
    try:
        tree = tmp / "skills"
        for s in FIVE:
            (tree / s).mkdir(parents=True)
            shutil.copy2(SKILLS / s / "SKILL.md", tree / s / "SKILL.md")
        for s in LITE_REQUIRED:
            shutil.copy2(lite_path(s), tree / s / "SKILL.lite.md")

        def run_c13():
            vc.errors.clear()
            old = vc.SKILLS
            vc.SKILLS = tree
            try:
                vc.check_lite()
            finally:
                vc.SKILLS = old
            return list(vc.errors)

        # 正例：原样三份 lite → 无报错
        errs = run_c13()
        check("T5-7a C13 正例：原样 lite 无报错", not errs, str(errs))

        # 负例 1：删 ① lite → 在位检查触发
        (tree / "bid-response-plan" / "SKILL.lite.md").unlink()
        errs = run_c13()
        check("T5-7b C13 负例：缺 lite 被抓出",
              any("缺少 SKILL.lite.md" in e for e in errs), str(errs))
        shutil.copy2(lite_path("bid-response-plan"), tree / "bid-response-plan" / "SKILL.lite.md")

        # 负例 2：② lite 加 frontmatter → 误加载防线触发
        p2 = tree / "bid-compliance-check" / "SKILL.lite.md"
        p2.write_text("---\nname: fake\n---\n" + lite_text("bid-compliance-check"), encoding="utf-8")
        errs = run_c13()
        check("T5-7c C13 负例：lite 带 frontmatter 被抓出",
              any("不得带 frontmatter" in e for e in errs), str(errs))
        shutil.copy2(lite_path("bid-compliance-check"), p2)

        # 负例 3：③ lite 铁律改一字 → 漂移检测触发
        p3 = tree / "bid-technical-proposal" / "SKILL.lite.md"
        p3.write_text(lite_text("bid-technical-proposal").replace("不编造事实", "不捏造事实"), encoding="utf-8")
        errs = run_c13()
        check("T5-7d C13 负例：lite 铁律漂移被抓出",
              any("铁律块与主 SKILL.md 不一致" in e for e in errs), str(errs))
        shutil.copy2(lite_path("bid-technical-proposal"), p3)

        # 负例 4：① lite 删至 2 处 L2 标注 → §9 硬性要求触发
        p1 = tree / "bid-response-plan" / "SKILL.lite.md"
        t1 = lite_text("bid-response-plan")
        t1 = t1.replace("【能力依赖：L2】", "【能力依赖：L2x】", 2)
        p1.write_text(t1, encoding="utf-8")
        errs = run_c13()
        check("T5-7e C13 负例：L2 标注不足 3 处被抓出",
              any("【能力依赖：L2】标注不足 3 处" in e for e in errs), str(errs))

        # 负例 5：④（非 LITE_REQUIRED）补 lite 但铁律漂移 → 前向兼容检查触发
        p4 = tree / "bid-docx-export" / "SKILL.lite.md"
        p4.write_text("# lite\n" + lite_text("bid-response-plan").replace("不编造事实", "不捏造事实"), encoding="utf-8")
        errs = run_c13()
        check("T5-7f C13 负例：④ 若有 lite 同样受铁律一致约束",
              any("bid-docx-export" in e and "不一致" in e for e in errs), str(errs))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # ---------- T5-8 validate_contract 全绿（含 C13） ----------
    env = dict(__import__("os").environ, PYTHONUTF8="1")
    r = subprocess.run([sys.executable, str(VC)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env)
    check("T5-8 validate_contract 全绿（C1–C13）", r.returncode == 0,
          r.stdout[-400:] if r.returncode else "")

    n_fail = sum(1 for _, ok, _ in results if not ok)
    print("\n===== 阶段 5 回归：%d 项，PASS %d / FAIL %d =====" %
          (len(results), len(results) - n_fail, n_fail))
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
