#!/usr/bin/env bash
# run_all_checks.sh —— skills-toolkit 一键校验（本地/CI 通用）
# 对齐 AGENTS.md「必跑命令」：契约闸门 C1–C13 + 阶段 1~6 回归 + 素材母库机检；
# 本机有设施时顺带跑计划书扫描与企业事实母库检查（见下）。
# 用法：bash tools/run_all_checks.sh
# 退出码：全部通过 0；任一检查失败 1（保持各脚本 rc 语义，不做二次包装）。
set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 2

PY=python
PASS=0
FAIL=0

run() {
  local label="$1"; shift
  echo ""
  echo "===== $label ====="
  if "$@" >/tmp/checks_$$.log 2>&1; then
    PASS=$((PASS + 1))
    echo ">>> PASS: $label"
  else
    FAIL=$((FAIL + 1))
    echo ">>> FAIL: $label (rc=$?)"
    sed -n '1,80p' /tmp/checks_$$.log
  fi
}

run "validate_contract (C1–C13)"        "$PY" tests/validate_contract.py
run "stage1 regression (32 项)"          "$PY" tests/test_stage1_regression.py
run "stage2 regression (73 项)"          "$PY" tests/test_stage2_regression.py
run "stage3 regression (74 项)"          "$PY" tests/test_stage3_regression.py
run "stage4 regression (44 项)"          "$PY" tests/test_stage4_regression.py
run "stage5 regression (28 项)"          "$PY" tests/test_stage5_regression.py
run "stage6 regression (14 项)"          "$PY" tests/test_stage6_regression.py
run "check_knowledge (K1–K9) 空库绿"     "$PY" tests/check_knowledge.py

# 计划书扫描：plan 文档在仓库被 .gitignore 排除（本地草稿），仅本机存在时跑
PLAN="docs/投标文件Skill建设计划_v0.21.md"
if [ -f "$PLAN" ]; then
  run "scan_doc 计划书 v0.21 (D1–D6)"  "$PY" tests/scan_doc.py "$PLAN"
else
  echo ""
  echo "===== scan_doc 计划书 ====="
  echo ">>> SKIP: $PLAN 不存在（计划书为本地草稿，不入仓库）"
fi

# 企业事实母库：母库在仓库外本地目录，设置 FACTS_LIB 环境变量才跑
if [ -n "${FACTS_LIB:-}" ] && [ -d "${FACTS_LIB:-}" ]; then
  run "check_facts_library (L1–L8)"      "$PY" tests/check_facts_library.py --library "$FACTS_LIB"
else
  echo ""
  echo "===== check_facts_library ====="
  echo ">>> SKIP: 未设置 FACTS_LIB 或目录不存在（本机专用，CI 不跑）"
fi

rm -f /tmp/checks_$$.log
echo ""
echo "=========================================="
echo "通过 $PASS 项 / 失败 $FAIL 项"
[ "$FAIL" -eq 0 ] && echo "结果: PASS" || echo "结果: FAIL"
[ "$FAIL" -eq 0 ]