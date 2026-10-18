# bid-compliance-check（② 投标合规自检）

套件第 ② 环，**守废标红线**。分两段：②-A 查任务卡覆盖，②-B 查正文响应。只报事实态（已响应／响应不足／未响应），不判"是否废标"。

## 输入

| 段 | 入口 stage | 前置产物 |
|---|---|---|
| ②-A | `plan_confirmed` | `00_metadata.json`、`01`、`01b`、`01c`、`03_bid-plan.json`、`04_outline.json`、`02_facts` |
| ②-B | `writing` | 上述全部 ＋ `05_chapters/*.md`、`06_compliance/` |

**不读招标原文**：形式要求一律取自 `01c.typography`（`seal`/`binding`/`page_limit`）与 `01.clauses[]` 中 `review_stage = form` 的条目；字段缺失即判 `blocked_by_contract` 并指回 ①。

## 产出

`06_compliance/`：
- **②-A（阶段 1 已实产）**：`compliance-report.md`、`compliance-report.json`、`form-check.md`、`business-check.md`、`deviation-table.md`
- **②-B（阶段 2 规划，未实产）**：`consistency-issues.md`、`similarity-check.md`

## 检查类

A 废标项｜B 响应偏离表｜G 评分违规识别（只标注不定性）｜C 形式与一致性｜F 资质时效（三态：`fact_missing`/`expired`/`expiring_soon`）｜D 商务表齐全性｜E 雷同自查。

**F 类时点**：在 ②-A 完成，与 `00_metadata.deadline` 比对；`external_missing`/`fact_missing` 属资料缺口（回退 ① 补录，不计废标风险），`expired` 才是废标风险。

## 关卡

- **G3（②-A 出口）**：废标报告逐条处置 → `check_confirmed`
- **G5（②-B 出口）**：成稿终检＋背对背复核差异清单闭环 → `recheck_confirmed`

## 版本

`0.2.0`（阶段 1：②-A 覆盖检查 A/G/D/F 已实装、C/B 部分实装；②-B 与 E 类雷同自查随阶段 2 交付）

## 依赖

`references/流水线交接约定.md`、`references/常见错误.md`、`assets/*.schema.*`。
