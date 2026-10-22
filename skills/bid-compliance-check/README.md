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
- **②-B（v0.4.0 已实产）**：`deviation-table.md`（②-B 模式逐行判定，覆盖写）、`consistency-issues.md`（跨章一致性）、`compliance-report.md` 追加「## 十一、②-B 成稿响应复查」节（保留 ②-A 记录）；`similarity-check.md`（E 雷同）仍属规划

## ②-B 运行（v0.4.0）

`python scripts/check_compliance.py --bid <项目/bid目录> --mode B`（Python ≥ 3.12）：
- 入口 `stage=writing`（重跑态 `rechecking` 合法）；执行中写回 `rechecking`；缺前置阻断零产物（rc=2）
- **前置人工件**：`08_business/deviation-table.md`（按 `references/响应偏离表模板.md` 填写，首列条目id 照录 `01b` 主键）
- A-lite 任务卡成稿三态（已响应/响应不足〔残留【待填】给位置〕/未响应/证据类）＋ B 偏离表逐行（跳条/多行/重行/照抄/空白判定/负偏离废标级单列/出处断链）＋ F 复述 ②-A 结论
- 退出码：0=无错误；1=存在错误/废标级负偏离（G5 须闭环）；2=前置缺失
- C 类另跑 `python scripts/check_consistency.py --bid <bid>`（全套件唯一实现）：工期/金额同语义多值 ⚠️＋名称变体＋同值异形（中文大写归一）不误报＋位置粒度到行

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

`0.5.1`（专家复核批次 1–4 修复：`check_consistency.py` 关键日期槽〔截止/开标/递交/有效期同槽多值 ⚠️ 抬 rc=1〕＋金额同值异形死条件修复；`check_compliance.py` `qual_timing` 三元组契约〔`f_qual_timing.status/items`，④ gate 联动阻断〕＋draft 章警告不阻断＋前置缺章阻断 rc=2；`check_business.py --mode B` 行内大小写金额等值核对）；`0.5.0`（阶段 5：新增 `SKILL.lite.md` L0 纯对话版轻量提示词——A 段覆盖走查/F 类时效三态走查/B 段成稿响应走查，每步【能力依赖：L2】+降级指令、铁律自包含、R7 状态快照；一致性由 `validate_contract` C13 机检；脚本零变化）；`0.4.0`（②-B 成稿响应检查实装，阶段 2 第二步：`check_compliance.py --mode B`〔A-lite 三态/B 偏离表逐行/F 复核/G5 指引，退出码 0/1/2〕；`check_consistency.py` v0.4.0〔位置粒度＋工期/金额同语义多值 ⚠️＋中文大写归一同值异形不误报〕；`响应偏离表模板.md` 定人工填写落点 `08_business/deviation-table.md`＋条目id 主键列。经示例市真基 1266 条偏离表〔4 缺陷全检出〕与合成回归 T2-9/T2-10 验证）

## 依赖

`references/`（上述七件 ＋ `流水线交接约定.md`、`常见错误.md`）、`assets/*.schema.*`。
脚本：`check_compliance.py`（②-A ＋ ②-B `--mode B`）、`check_business.py`（M8）、`check_consistency.py`（②-B 跨章一致性，全套件唯一实现）。
轻量版：`SKILL.lite.md`（L0 纯对话平台粘贴用；无 frontmatter，不进 `skills-lock.json`）。
