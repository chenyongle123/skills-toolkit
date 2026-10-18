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

**操作细则**（`references/`，v0.3.0 补齐）：

| 文件 | 覆盖 |
|---|---|
| `判词库-投标侧.md` | 漏响应扫描关键词（派生自 ⓪ 判词库.md v1.5.0，扫描前必读） |
| `废标项比对方法.md` | A 类：主覆盖比对＋跨类否决级补充扫描＋孤儿卡 |
| `响应偏离表模板.md` | B 类：行来源＝`01b` 逐行；禁照抄原文/正偏离须具体/负偏离分级 |
| `形式核对清单.md` | C 类：形式要求来源对照＋②-A/②-B 分工＋跨章一致性 |
| `暗标匿名检查.md` | D10/D11：语境二分＋8 项终检＋高危遗漏位 |
| `雷同自查清单.md` | 计划书 §8.6：四道防线＋套话密度＋结构模板化＋独立性自查 |
| `资质时效核查.md` | F 类：四态判定＋换证窗口口径＋②-A/②-B 分工 |

**F 类时点**：在 ②-A 完成，与 `00_metadata.deadline` 比对；`external_missing`/`fact_missing` 属资料缺口（回退 ① 补录，不计废标风险），`expired` 才是废标风险。

## 关卡

- **G3（②-A 出口）**：废标报告逐条处置 → `check_confirmed`
- **G5（②-B 出口）**：成稿终检＋背对背复核差异清单闭环 → `recheck_confirmed`

## 版本

`0.3.0`（references 七件补齐，计划书 §3.5 接管必建项落地；新增 `scripts/check_consistency.py` 跨章一致性骨架版——全套件唯一实现；②-B 与 E 类雷同自查仍随阶段 2 交付）

## 依赖

`references/`（上述七件 ＋ `流水线交接约定.md`、`常见错误.md`）、`assets/*.schema.*`。
脚本：`check_compliance.py`（②-A）、`check_business.py`（M8）、`check_consistency.py`（②-B 跨章一致性骨架版）。
