# Changelog

本仓库所有技能的版本变更记录。格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [SemVer](https://semver.org/lang/zh-CN/)。

Tag 约定：技能版本 tag 为 `技能名/vX.Y.Z`；仓库级变更 tag 为 `repo/vX.Y.Z`。

## [repo/v1.4.0] - 2026-10-18

> 阶段 1 开发缺口补齐：`check_business.py`（M8 商务表专项检查）新建 + D5 评分表分值闭合验算脚本化。

### Added

- **`bid-compliance-check/scripts/check_business.py`（新建）**：M8 商务表专项检查，对应计划书 §11.2 阶段 1 验收第 9 条与 §5 目录树。
  该文件此前被 §5 点名、并被回归标记 M7（`regression_markers.json`）锁定 `must_contain: ["check_business.py"]`，**但仓库内从未实装**——属阶段 1 收口的真实缺口。检查项：
  - **B1 零金额（阻断级）**：扫描 `03c` 业务语义字段（`name`/`required_fields`/`consistency_rules`）与 `seal`，检出金额即以退出码 1 报出。覆盖四类形态——数字+金额单位、货币符号、中文大写（如「壹拾贰万元整」）、千分位；`seal` 仅查强特征以放行「按前附表3.4.1」类条款号引用，并豁免 `id`/`tender_page`/`chapter_id`/`copies`/`filled_file` 等结构位置字段。
  - B2 `required_fields` 齐备、B3 `seal` 齐备、B4 `chapter_id` 解析到 `01c`、B5 `consistency_rules` 三条硬性规则覆盖。
  - **B7 诚实标注**：「03c 表数＝招标商务格式章要求表数」因 ② 不读招标原文而**不可独立机检**，标注以 ① 抽取声明为准，不作无源断言。
  - **职责边界**：不重复 `check_compliance.py` 已实现的 D 类「表格↔任务卡一一对应」。
- **`tender-document-review` D5 分值闭合验算脚本化**：`emit_facts.py` 新增 `--expected-total <明示总分>`，自动求 `scoring.items[].points` 之和并与明示总分比对；未录入或不等**均告警**（不静默通过）。
  此前该规则仅写在 ⓪ `SKILL.md` 第 234 行「分值闭合验算（必做）」，脚本无对应实现——属规则与实现的**契约漂移**，本次补齐。明示总分须人工从原文录入后传入，AI 不得自动解析招标文件后直接采用（同 `deadline` 口径）。

### Changed

- `06_compliance/business-check.*` 落点移交 `check_business.py` 唯一写入；`check_compliance.py` 不再重复写同一文件（避免两脚本互相覆盖）。其 D 类「商务表↔任务卡一一对应」结论仍完整保留在 `compliance-report.md/json` 的 `business_forms` 字段，信息不丢。
- 版本与锁：`tender-document-review` 1.4.0→**1.4.1**、`bid-compliance-check` 0.2.1→**0.2.2**，`skills-lock.json` 经 `validate_contract.py --write-lock` 刷新。

### Tests

- **M8 金额拦截**：4 类注入（数字 `1234567.89元`／货币符号 `¥1000000`／中文大写 `壹拾贰万元整`／千分位 `1,234,567元`）**全部阻断**（rc=1）；3 类负例（合法字段名「投标总报价（大写）」、含大写数字但非金额「贰级资质」、seal 条款号「按前附表3.4.1」）**全部放行、无误报**。
- **D5 闭合三情形**：不录明示总分→告警「合计 30 未经闭合验算，不得静默采用」；录 30（＝合计）→闭合无告警；录 100→报「合计 30 ≠ 100（差异 -70），须回原文复核」。rc 均为 0（警告非硬阻断，符合 ⓪ SKILL.md 口径）。
- **落点与回归**：删掉 `business-check.md` 后跑 `check_compliance.py` 确认未被重建（移交生效），再由 `check_business.py` 写入；`check_compliance.py` 覆盖计数与改造前一致（废标 11／资格 7／商务表 24/24／孤儿 0／F 类 expired），**无回归**；M 层 `validate_contract`（C1–C11+C5b）PASS。

### Notes

- **中文大写金额正则首版误加 `$` 锚点**，导致「壹拾贰万元整」漏检（首轮测试 rc=0、未阻断），而中文大写恰是最典型的投标报价写法。已修正为「大写数字起 + 进位/数字 + 可选万/亿 + **必有元/圆** + 可选整」，并要求必有「元/圆」以避免「贰级资质」类误报。此为**测试实际抓出的缺陷**，非事后补述；修正后 4 类形态全拦下、3 类负例全放行。
- 「表数＝招标格式章要求表数」（§11.2 #9 前半）在当前架构下**无法独立机检**：① 的 `BUSINESS_FORMS` 为硬编码常量（bf-01~bf-24，取自示例市项目第七章），② 不读招标原文、03c schema 亦无期望表数字段。已如实标注为「以 ① 抽取声明为准」，未伪造通过。

## [delivery-audit/v1.1.3] - 2026-10-18

> 修正 `README.md` 与 `SKILL.md`（v1.1.2）两处自相矛盾（专家审核发现）；技能能力不变。

### Fixed

- `README.md` 核心机制表：铁律由「五条（L1–L5）：记忆非证据／引用须落盘／数字须复算／时效须当日／校验优先」改为**六条（L1–L6）：记忆非证据／存在≠准确／完成即怀疑／同源隔离／校验优先／能机判不人判**，与 SKILL.md 第 100 行逐字对齐。
- `README.md` 核心机制表：输出态由「三态：✅／⚠️ SELF-ONLY／❌」改为**四态：✅ VERIFIED／⚠️ SELF-ONLY／⚠️ UNVERIFIED／❌ REFUTED**，补关键降级态 UNVERIFIED，与 SKILL.md 第 268 行「输出契约（四态）」一致。

## [bid-compliance-check/v0.2.1] - 2026-10-18

> 修 X 层盲审（换模型交叉验证）发现的 3 处硬伤（H1/H2/H1-spec）；能力范围不变，向后兼容。

### Fixed

- **H1 · F 类资质时效改读结构化事实库**：`check_compliance.py` 原仅扫描 `02_facts.md` 正则，而 `facts.schema.yaml` 规定 ②③ 解析 `02_facts.yaml`（qual-/pers- 含 `valid_to`），导致 P0 最高频废标点（R14 证书有效期早于截止日）在本管线恒 `fact_missing`、过期判定从未真跑。现 `_load_structured_facts` 优先读 `02_facts.yaml`（PyYAML 可用时完整解析，**不可用时零依赖极简解析兜底**，避免静默降级），缺失再退化扫描 `02_facts.md`；`qual_timing` 据 `valid_to` 与 `00_metadata.deadline` 真实比对，输出 `expired`/`expiring_soon`/`stated`/`fact_missing`。
- **H2 · 未响应条款 `status` 不通过产出 schema**：原对未匹配条款写 `status="未响应"`，但 `compliance-report.schema.json` 的 `waste[].status` enum 仅 `["covered","no_card"]`，恰在「漏响应废标项」路径产出非法 JSON。现未匹配条款 `status="no_card"`（disposition 仍为 `未响应`，属新枚举三态之一），产出 JSON 经 jsonschema 校验 0 错误。
- **H1-spec · disposition 五态统一为计划书 D5 三态**：原实装五态（含「已响应(就绪)/响应不足(待澄清)/响应不足(缺事实库)/响应不足(其他)」），与计划书套件级 D5（第 243 行）「统一为已响应/响应不足/未响应 + needs_original」冲突。现 `disposition ∈ {已响应, 响应不足, 未响应}`，「响应不足」细分原因（待澄清/缺事实库/其他）移至新增 `reason` 字段，schema 同步收敛枚举并加 `reason`。

### Changed

- `skills-lock.json`：`bid-compliance-check` 版本刷新为 0.2.1，`compliance-report.schema.json` hash 随枚举改动更新（`validate_contract.py --write-lock` 重写）。
- `bid-compliance-check/SKILL.md`：版本 0.2.0→0.2.1；F 类能力说明改为「优先解析结构化 02_facts.yaml/.json」；运行说明注明 F 类优先读 yaml。

### Notes

- 验证：示例市 100MW 风电样本副本注入结构化 `02_facts.yaml`（含过期＋换证窗口＋有效三类），重跑 `check_compliance.py` → `f_status=expired`，明细逐条正确；覆盖计数（废标11/资格7/商务24/孤儿0）与改造前一致，无回归。
- 章节树通用化（专家遗留建议 #2）、`g3_disposition` 自由串收紧（X 审 M5）属后续阶段/中等问题，本轮未动。

## [repo/v1.3.0] - 2026-10-18

### Added

- 新增投标文件编写套件四技能 ①—④（`bid-response-plan` / `bid-compliance-check` / `bid-technical-proposal` / `bid-docx-export`），含阶段 0 骨架与 ①② v0.2.0 阶段 1 首批实现
- `tests/`：契约校验三件（`validate_contract.py` C1–C11＋C5b、`scan_doc.py` D1–D6、`mini_schema.py`）+ `fixtures/` 8 份
- `skills-lock.json`：五技能版本 + 8 个契约 schema hash 与副本清单
- `docs/`：v0.1–v0.16 各轮审核判断、交叉验证报告、阶段 0 验收记录、触发实测记录、回归标记 `regression_markers.json`
- `business-contract-review` 补 README

### Changed

- README 技能一览表：版本刷新 + 四技能条目 + 触发边界与 lock 管控边界说明（外挂技能不入 lock）

## [bid-response-plan/v0.2.0] / [bid-compliance-check/v0.2.0] - 2026-10-18

> 阶段 1 首批落地：① 任务卡生成实装、②-A 覆盖检查实装。③④ 保持 v0.1.1 骨架不动。

### Added（① bid-response-plan v0.2.0）

- `scripts/build_bid_plan.py`：读 `00_metadata.json`（stage=reviewed）+ `01_tender-facts.json`（0.4），产出 `01b`/`01c`/`03_bid-plan.json`（0.2，含 `preconditions`）/`03c`/`04_outline.json` 与素材缺口清单；零三方依赖可跑，可选 `jsonschema` 做完整校验
- `references/` 新增 6 份：任务卡模板、目录骨架规则、七类-六环节映射、技术规范条目抽取规则、格式章与排版要求抽取规则、商务表格抽取规则
- SKILL.md §三 主流程 8 步（含 G1 闸门）、§七 能力范围表

### Added（② bid-compliance-check v0.2.0）

- `scripts/check_compliance.py`：②-A 覆盖检查实装（A 废标/资格覆盖、G 评分违规识别——只标注不定性、D 商务表齐全性、F 资质时效四态、C 形式字段部分），`--mode B` 为阶段 2 占位；产出 `06_compliance/{compliance-report.md,compliance-report.json,form-check.md,business-check.md,deviation-table.md}`
- `assets/compliance-report.schema.json`（阶段 0 未建，本版补齐并入 lock）

### Changed

- ①② frontmatter 0.1.2/0.1.1 → 0.2.0；`skills-lock.json` 升 `kit/v0.2.0-stage1`（schema 7→8）
- ① `01c` 章节树常量固化首测项目第七章结构，换项目须重新抽取覆盖 `FORMAT_CHAPTERS`

### Notes

- 契约机检 C1–C11＋C5b 全绿；`scan_doc.py` 对计划书/验收记录 D1–D6 全绿
- ②-A 换模型盲审工单已生成（`workdir/xaudit-2026-10-18-02A-code.md` / `-spec.md`），**回执未回，X 层未闭环**，本版相关声明效力以机检＋自审为限
- 阶段 1 验收余项待执行：真实招标文件试跑（两轨对账、评分分值闭合验算、跳步拦截实测）、平台端到端触发验证（须用户新会话亲自发话）

## [delivery-audit/v1.1.2] - 2026-10-17

> 补录条目（v1.1.0–v1.1.2 未及时入库）。

### Added

- v1.1.0：M 层机器自检（M1–M7，`scripts/scan_doc.py`）、X 层换模型交叉验证（盲审工单模板 `references/cross-audit-template.md`）、SELF-ONLY 四态输出、结构性变更后强制回扫（§7）
- v1.1.1：M6 版本一致检查
- v1.1.2：M7 回归标记（防假修复）——JSON 钉死"错词必须消失/对词必须在节内出现"；强制"完成/已修复"声明须 M7 绿 + X 层完成，否则最高标 ⚠️ SELF-ONLY 并显式注明未经独立复核

### Fixed

- v1.1.1：M2 两类误报

## [bid-response-plan/v0.1.2] / [bid-compliance-check/v0.1.1] / [bid-technical-proposal/v0.1.1] / [bid-docx-export/v0.1.1] - 2026-10-17

> 触发实测驱动的 description 修订 + `bid-plan` 契约 0.2。**能力范围未变**（四技能仍是骨架版，不产出任务卡/检查/正文/导出）。

### Added

- `bid-plan.schema.json` 0.1→0.2：顶层新增 `preconditions`——`p-0001` 恒为「补遗/澄清文件对照」，`result` 三态（pass/fail/unknown），`blocking` 为 true；**不列入 `required`**，0.1 旧文件仍合法
- `tests/validate_contract.py` 新增 **C11**：校验补遗对照前置项在位、首项为 `p-0001`、非 pass 必须有 evidence

### Changed

- ① description：补「帮我写投标文件」「帮我编投标文件」触发语；改为「章名逐字取自 01c，不回读招标原文」
- ② description：`投标文件合规自检` → `投标响应合规自检`（去掉与 ⓪ 抢触发的裸词）
- ③ description：加「须已有任务卡」「不写整套投标文件、不写商务标/资格标/报价表」「用户说…属全流程入口，不属本技能」
- ④ description：`投标文件排版` → `投标材料排版`、`把标书装订成 PDF` → `把成稿装订成 PDF`；加「须已有成稿」「问格式章要求属 ⓪，本技能不做解读」
- `--write-lock` 修复：改版后不再因"与旧 lock 比对失败"而拒绝写入（原先会导致改版死锁）

### Notes

- 触发实测共四轮（含 2 次无效：一次因注入截断、一次因运行目录未同步而读到旧 description），三条阻断级指标最终通过；效力边界与残余风险见 `docs/v0.16_触发实测记录.md`
- 实测后按既定方案只保留 ① 在运行目录，②③④ 已卸载，待各自阶段上线再装

## [tender-document-review/v1.4.0] - 2026-10-17

> 追加"与套件衔接"一节：声明受套件总则约束、出口创建 `00_metadata.json`、输出末尾加交接提示。**提取规则（11 条铁律、7 步流程、七类输出格式）一字未改**；`schema_version` 仍为 0.4、`source_rule_seq` 仍为 10。

### Added

- SKILL.md 第十一节「与投标文件编写套件的衔接」：总则归属（两套编号分阶段生效）、状态文件（只写 `schema_version` 与 `stage=reviewed`，不代填截止日/项目信息）、交接提示行
- `scripts/emit_facts.py` 的 `FALLBACK_SKILL_VERSION` 同步为 `1.4.0`

### Changed

- `assets/tender-facts.schema.json` 自述由"计划书 §6.2 回填待 v0.16 合并"改为"已回填 v0.16 计划书 §6.2"

## [bid-response-plan/v0.1.0] / [bid-compliance-check/v0.1.0] / [bid-technical-proposal/v0.1.0] / [bid-docx-export/v0.1.0] - 2026-10-17

> 阶段 0 骨架版：只落"结构性契约"，不落业务规则。

### Added

- 四技能 SKILL.md：定位与边界、入口校验（stage / 前置产物 / 契约版本）、8 条铁律（逐字一致）、出口指路、本版能力范围声明
- `references/流水线交接约定.md` **四份逐字一致**（sha256 相同）：状态机责任表、四步入口校验、阻断输出格式、出口五项写回、G1–G5 归属、回退规则、lock 三级降级
- `references/常见错误.md`：8 条铁律反例（错误做法/为什么错/正确做法/判定线索）
- `assets/` 契约 schema 落位（见 tests/validate_contract.py）

### Notes

- 骨架版对"前置齐备但要求产出"的请求输出「能力未实现」，**不生成半成品**；任务卡/检查/正文/导出分别随阶段 1/2/3 交付
- 跨章一致性检查全套件只保留 ② 一份实现，③ 不复制

## [tender-document-review/v1.3.1] - 2026-10-17

> 专家复审（换模型）后的文档/契约一致性补丁，无提取规则变更；`source_rule_seq` 仍为 10，`schema_version` 仍为 0.4（向后兼容）。

### Fixed

- **M1 值状态口径对齐**：SKILL.md「值状态」判定措辞由"每条必判/每条填"放宽为"推荐必做；机读字段 `value_state` 可选，未判定置空串"，与 schema（v0.16 delta D3 明确为可选、不进 required）及判词库一致
- **M6 emit_facts.py 注释修正**：`clauses[].id` 缺省生成与"稳定主键、排序变化不改"自相矛盾——改为"自填 id 才是稳定主键；依赖缺省 id 时顺序变化 id 即变"
- **M7 schema 自述软化**：不再声称"与计划 §6.2 唯一真源完全一致"，改为"与 v0.16 delta 定义一致（§6.2 回填待 v0.16 合并）"

### Changed

- **M3 命名统一**：「值三态」→「值状态（四值）」（SKILL.md + 判词库 v10 + v0.16 delta D3）
- **M4 判词库 v10 标题**：「限价异名与形态四态分流」→「限价异名与形态六值分流（四形态＋两兜底）」
- **M2 清单模板补列**：七类表通用字段增「值状态」列，⑤ 类表增「限价形态」列，落实四重呼应
- **M5 skill README**：「机读产物」说明补 v1.3.0 增量；「四重呼应」扩为「六重呼应」（增 assets schema + emit_facts.py）
- 版本 `1.3.0` → `1.3.1`（frontmatter / 正文 / 第十节示例 / schema 自述等自引用同步）

## [repo/v1.2.0] - 2026-10-17

### Changed

- README 技能一览表 `tender-document-review` 版本号 v1.1.0 → v1.3.0
- CHANGELOG 限价四态枚举名由错误写法 `pending_clarification / provisional_price` 修正为 `pending / tentative`（与 schema / SKILL.md / delta 对齐）

## [repo/v1.1.0] - 2026-10-17

### Added

- 新增仓库级 `docs/` 目录，收纳与技能运行无关的开发设计文档

### Changed

- 开发过程文档迁出技能包：`未来升级方向备忘` 脱敏后移至 `docs/`，`v8行为验证报告` 删除（结论已提炼进规则变更记录）

## [tender-document-review/v1.3.0] - 2026-10-17

> 说明：v1.2.0（机读产物）当时未单独提交，其内容随本版本一并入库，故此处合并记录。

### Added（v1.2.0 机读产物）

- 第十节「机读产物（tender-facts.json）」：七类清单同步输出 JSON（套件语境即 `01_tender-facts.json`），字段与套件契约唯一真源逐字段一致；**不新增任何提取与判断**，JSON 与 Markdown 不一致时以 Markdown 为准
- `assets/tender-facts.schema.json`：机读产物字段约束
- `scripts/emit_facts.py`：零依赖序列化便利脚本，含结构校验与条目数守恒自检（只报告差异，不自动补猜）
- `references/判词库.md`：「规则变更记录」追加 v9/v10 两条

### Added（v1.3.0 提取规则增量，源自 13 份真实招标文件实测）

- **补遗改强制输入**：招标文件正本＋全部补遗/答疑为强制输入，缺失即阻断（原为「可含」）
- **限价四态判定**：`amount / rate / pending / tentative / none / unmentioned`（与 schema `price_cap_form` 枚举一致），并扫异名（最高限价、控制价、控制费率、下浮率门槛、暂定价、第 N 包）；含「模板残留」裁定——前附表与正文不一致时以前附表为准并标注
- **值三态判定**：`stated / unstated / draft_blank / external_missing`，区分「文件未载明」「留白未定稿」「外指文件未随附」三种缺失性质
- **无分页文档出处规范**：Word 等无稳定页码文档用「章 → 条款号 → 段落号/表号」四元组定位

### Fixed

- 评分表增加**分值闭合验算**：各评分表分值合计须等于该表总分，不等即列为待澄清
- `description` 删除裸触发词「投标文件、标书」（改为「招标文件中的『投标文件格式』章」），避免与套件下游技能路由双命中

### Changed

- 契约版本 `schema_version / contract_schema_version` 由 `0.3` 升至 `0.4`（新增 `price_cap_form`、`value_state` 两个**可选**字段，向后兼容）

## [tender-document-review/v1.1.2] - 2026-10-17

### Fixed

- **第 7 步补硬前置**：法定情形核对卡加载原仅写在 20 项核查清单中后段（第 261 行），无「本步首个动作」标记，实测在 184 页样本上被跳过导致该分项自检未执行。现于第 7 步开头加 🔴 硬前置，并规定"未加载法定卡即宣告自检完成 → 须在交付审查中标 ⚠️ UNVERIFIED，不得标 ✅"

## [tender-document-review/v1.1.1] - 2026-10-17

### Changed

- **交付自检闸门默认值反置**：`FRESH + INDEP` 增加「无独立工具时，关键数值一律默认标 ⚠️ UNVERIFIED」的硬规则，举证责任交给复核方；明确"通读一遍"与"两处引自同一抽取结果"均不构成独立复核
- **参考文件改为渐进加载**：`判词库.md` 在第 4 步起始加载、`清单模板.md` 在第 2/5 步加载、`法定情形核对卡.md` 在第 7 步加载；第 1、3 步不加载任何参考文件。第 2、4、5 步各加「本步首个动作」硬前置指令，防止漏加载导致整类漏项
- 技能 README 补充加载时机说明

## [tender-document-review/v1.1.0] - 2026-10-17

### Changed

- **发布包净化**：移除 `references/v8行为验证报告.md`（含真实项目名与本地绝对路径，违反"个体内容不进技能"原则）与 `references/未来升级方向备忘.md`（开发决策记录，非运行所需）；技能包现仅含 SKILL.md + README + 3 份运行必需参考文件
- **版本体系单轨化**：取消"技能版本 / 规则版本"双轨编号，技能版本号 `1.1.0` 即唯一版本；`判词库.md` 的「版本记录」改为「规则变更记录（历史，仅供追溯）」，不再启用 vN 编号
- README 目录清单与实际文件对齐

## [repo/v1.0.0] - 2026-10-17

### Added

- 仓库骨架：`skills/` 目录结构、README、LICENSE（CC BY-NC 4.0）、CHANGELOG、.gitignore
- 初始收录三个技能（均 v1.0.0，见下）

## [tender-document-review/v1.0.0] - 2026-10-15

### Added

- 投标方视角招标文件审查技能首发：七类结构化清单（时间节点与流程/资格条件/废标情形/评标定标/保证金商务/合同约束/形式程序）
- 内部规则版本 v9（`references/判词库.md`）
- 清单模板、法定情形核对卡、行为验证报告

## [business-contract-review/v1.0.0] - 2026-10-10

### Added

- 中国法商务合同审核技能首发：四类合同（施工/EPC分包、物资采购、技术服务、招标代理/劳务）条款级审查
- 红黄绿三级风险分级 + redline 修改建议 + 谈判策略
- 通用条款叠加检查、成套文件解释顺序、内部一致性核查
- 第九步交付前收口自检（法律类 11 项）

## [delivery-audit/v1.0.0] - 2026-10-10

### Added

- 交付前审查技能首发：五条铁律（L1 记忆非证据 ~ L5 校验优先）
- 四段闸门（CLAIM → EVIDENCE → FRESH+INDEP → REDOUBT）
- 三态输出（✅/⚠️/❌）与四领域清单（数据/文档/电气/法律）
