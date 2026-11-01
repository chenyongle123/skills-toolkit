# 试跑记录：示例市真基 machine-chain 至 ② G3

## 头信息

- 日期：2026-10-21（阶段 4 WP1 冒烟＋回归收口）
- 对象：`workdir/acceptance/bid_base`（示例市 100MW 风电 EPC 真基副本，阶段 1 A 系列建立，stage=checking）
- 环境：⓪ v1.5.1 / ① v0.21.0 / ② v0.4.0 / ③ v0.2.0 / ④ v0.2.0；驱动器 `tests/run_acceptance.py`（本阶段新建）；Windows / Python 3.14.6；jsonschema 未装（validate_plan 降 WARN 不阻断）
- 操作模型：z-ai/glm-5.3（opcteam 会话内）

## 目的

验证阶段 4 E2E 驱动器（run_acceptance）在**真实项目产物**上的两件事：
1. verify（只读核查）在真基上给出的 frontier/结论是否与交接约定一致；
2. --run（临时副本串联）能否把真基推进到下一人工关卡，且停点正确。

## 环境与命令

```powershell
# verify（真基，只读）
$env:PYTHONUTF8='1'
python tests/run_acceptance.py verify --bid workdir/acceptance/bid_base

# --run（%TEMP% 临时副本，真基只读）
python tests/run_acceptance.py run --bid workdir/acceptance/bid_base
```

rc 读取：python 进程退出码（0=PASS/停点正常，2=阻断）。

## 步骤与结果

1. **verify 真基**：rc=0，结论 PASS。
   - frontier = `② 关卡 G3`（原因：废标检查报告处置待人工完成）——与基线状态（stage=checking，02 已产出、check_confirmed 未写）一致。
   - ③ 双检（check_facts/word_count）skip：无 05_chapters 目录，属预期降级。
   - validate_plan：rc=0，jsonschema 缺失仅 WARN。
2. **--run 临时副本**（真基本体全程只读，副本在 %TEMP%）：
   - ① `build_bid_plan` 全量重建：01b 1266 条、01c 42 章、03/03c/04 及素材缺口清单——与阶段 1 A 系列冻结基线数量一致；
   - 停 `① 关卡 G2＋G1（人工）`；人工在副本写 plan_confirmed 后续跑；
   - ②-A `check_compliance --mode A`＋`check_business --mode A`：rc=0；
   - 停 `② 关卡 G3（人工）`——副本止步于此，未再推进。
3. **同日合成回归**：`tests/test_stage4_regression.py` 44/44 全绿（合成数据，从 ⓪ 起步件到 ④ exported＋终态 verify PASS 的全链 E2E＋负例）。列此仅作机检面证据，**不属真实项目试跑**（合成数据结论不进 evals，此条为显式声明例外）。

## 停点与原因

- 真基/副本停 G3 ＝ ②-A 报告中的响应不足/未响应/需原件核对项须人工逐条处置（交接约定 §六），机器不代写 check_confirmed。
- ③ 写作及以后（G4/G5/④ 导出）**未在真基执行**——真实章节写作是 LLM 内容工作，超出 machine-chain 冒烟范围（合成侧由 T4-1 覆盖）。

## 发现的问题

- 阻断级：无。
- 信息级：① 02_facts 缺失 → 任务卡 blocked_by_facts 显式告警（符合交接约定设计）；② jsonschema 未装 → 01 结构子集校验降级（环境项，非缺陷）。

## 结论与效力边界

- **证得**：机器链在真基上行为符合设计——verify 语义、frontier 推进、G2/G3 停点、人工确认后方续跑，与交接约定逐条吻合；① 全量重建产物数量与冻结基线一致（无漂移）。
- **未证**：人工关卡（G1–G5）的人工决策质量；③ 真实章节内容质量；真实平台触发/拒绝行为（见 `trigger-tests/`）；④ 在真实 Word 打开效果（仅合成侧验证）。
- 状态：**⚠️ SELF-ONLY**（未经换模型盲审，见 `cross-audit/`）。

