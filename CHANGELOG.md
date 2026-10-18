# Changelog

本仓库所有技能的版本变更记录。格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [SemVer](https://semver.org/lang/zh-CN/)。

Tag 约定：技能版本 tag 为 `技能名/vX.Y.Z`；仓库级变更 tag 为 `repo/vX.Y.Z`。

## [tender-document-review/v1.5.0] - 2026-10-18

> ⓪ 加权型评分闭合验算（阶段 1 验收 #0 根因修复）：schema 三字段 + `emit_facts.py` 双口径。`schema_version`/`contract_schema_version` 保持 `0.4`（可选字段追加，同 v1.3.1 先例）。

### Added

- **`tender-facts.schema.json` 三字段（双副本字节一致）**：
  - `scoring.total_stated`（number）：招标文件明示总分，人工转录；
  - `scoring.weight_basis`（string）：加权口径原文依据摘录；
  - `scoring.items[].weight`（number）：条目权重（10% 录 `0.1`），仅加权型评分填。
  均标"v1.5.0 delta 新增，已回填计划书"，不进 `required`；`emit_facts.py` 校验形态兼容（加权型样本 `01_tender-facts.weighted.sample.json` 注册入 `FIXTURE_MAP`，过 C5）。
- **`emit_facts.py` 加权闭合口径**：任一条目带 `weight` 即按 Σ(分值×权重)＝明示总分验算，否则维持直接相加口径 Σ分值＝总分；两条口径均未录总分时告警"未经闭合验算，不得静默采用"；期望值解析链 `--expected-total`（人工录入，优先）→ 回退 `scoring.total_stated`（产物记录值，告警注明"未经人工复核"）；加权口径下 `weight_basis` 缺失或仅部分条目带 `weight` 均告警（权重不可追溯即不可信）；差异告警点名 `10% 录为 10 而非 0.1` 成因。

### Fixed

- `emit_facts.py` 直接相加分支提示语中 `10%＋` 等三处 `%` 未转义导致格式化崩溃（rc=1 traceback）——阶段 1 回归 R1-11 实测捕获，已转义 `%%`。

### Tests

- **`tests/test_stage1_regression.py` R1（12 项）**：加权口径闭合／差异-10／回退 total_stated／回退值注明来源／百分比误录点名／覆盖不全／缺 weight_basis／未录总分；直接相加口径四项回归（未录告警、30 闭合、差异-70、回退闭合）无回归。
- ⓪ `SKILL.md` 同步：frontmatter 1.5.0、第 5 步 D5 段重写为"两种评分口径"、10.2 JSON 示例与字段表补 3 行；计划书 §6.2 回填 delta（照 `price_cap_form` 先例）。

## [bid-response-plan/v0.5.0] - 2026-10-18

> ① 01b 第五章分阶段全量第二批（P1-d 续批）：新增 3.勘察设计要求 69 行、5.风电场调试、试运行和验收 5 行、6.施工工期要求 16 行（sp-017–106，全技能累计 106 行），散文章节拆分口径 v2 入 docstring；4/7/8/9 节挂起并按节登记段数/编号项数。

### Added

- **01b 新增 90 行（sp-017–sp-106）**：
  - 3.勘察设计要求（P3354–P3603，69 行）：3.1 勘察范围及要求 45 行编号项（基本要求 4/勘察范围 3/测量要求 13/地质要求 14/勘察报告 6/工程水文 6）；3.2 设计范围及要求 13 行（范围总述/施工图纸施工前 10 天提供/四项设计范围/六项交付份数/专项验收份数）；3.4＋3.5 设计依据原则与规范清单 11 行（3.5 规程规范清单 P3437–P3602 共 166 项按组 1 行登记，全清单以锚点段号范围追溯）；
  - 5.风电场调试、试运行和验收（P4478–P4483，5 行）：调试验收组织职责/验收组织主体/升压站调试验收标准/国标依据/整体竣工验收定义；
  - 6.施工工期要求（P4484–P4504，16 行）：进度计划 3 行/节点时间与考核 3 行/缺陷责任期 24 个月 1 行/进度管理 9 行；T38 承包人填写模板不拆行，录管辖段 P4490。
- **散文章节拆分口径 v2**（docstring 登记）：编号项逐条一行；无编号但独立成句的义务段逐段一行；技术参数行逐行一行；标准清单组每组一行；承包人填写模板表不拆行（录管辖段并在 requirement 注明表号）；引言/叙述背景/空段不抽——未抽类别以节段数范围登记，防漏条靠锚点可追溯。

### Changed

- `source.page_range` 与 docstring 覆盖状态改按节登记：已全量 4 节（2.性能指标 14＋3.勘察设计 69＋5.调试验收 5＋6.施工工期 16）／挂起 4 节（4.施工安装 P3604–P4477 共 818 段/编号项 105＋表 T33–T37；7.施工质量 P4505–P4891 共 351 段/编号项 91；8.竣工试验与验收 P4892–P5138 共 207 段/编号项 3＋表 T39；9.工程管理 P5139–P5389 共 243 段/编号项 69＋空白表 T40–T42）；`main()` 警告文案同步。
- ① `SKILL.md`：frontmatter 0.5.0＋版本头行。

### Tests

- `tests/check_01b_rawtext.py`：**106 条** raw_text 引文与招标原文逐行一致（PASS，一次通过）；输出改按节汇总（第五章已全量 104 行＋跨章节 2 行，带比较符可量化 10）。
- 示例市 `01b_spec-items.json` 再生为 106 行，按 `spec-items.schema.json`（0.1）jsonschema 校验 PASS；`test_stage1_regression.py` 24/24 无回退；`validate_contract.py` PASS。
- 验收记录第六节增补「P1-d 续批」小节：#1 维持部分通过（4/8 节），4/7/8/9 节挂起及段数登记入档。

## [bid-compliance-check/v0.3.1] - 2026-10-18

> ② 偏离表口径文案随 ① v0.5.0 同步（01b 基线 106 条、第五章已全量 4 节）。

### Changed

- `check_compliance.py` 偏离表口径行：「2.性能指标节已全量 14 行，第五章其余 8 节挂起」更新为「第五章已全量 4 节：2.性能指标 14 行＋3.勘察设计 69 行＋5.调试验收 5 行＋6.施工工期 16 行；挂起 4/7/8/9 节」——防 ② 输出与 ① 实际覆盖状态漂移。
- ② `SKILL.md`：frontmatter 0.3.1＋版本头行。

## [bid-response-plan/v0.4.0] - 2026-10-18

> ① 结构拆分＋契约落地＋01b 首批全量（P1-a/c/d）：按计划书 §5 目录树拆 5 个专职脚本、新增 `validate_plan.py` 全产物契约校验、`outline.schema.json` 落地（04 字段集对齐计划书 §6.2 D4 修正版）、01b 全量抽取第五章「2.性能指标」14 行。

### Added

- **五脚本拆分（计划书 §5 目录树）**：`parse_spec_items.py`（01b）/`parse_format_outline.py`（01c＋CID 单一真源）/`parse_business_forms.py`（03c）/`build_task_cards.py`（03/04/素材缺口清单）/`validate_plan.py`（全产物 schema 校验，只报告不修改；未装 `jsonschema` 降级结构自检并 WARN）；`build_bid_plan.py` 降为总编排器（CLI 不变，R2 端到端回归零改动通过）。各 parse 脚本 docstring 明确诚实定位：**人工抽取常量的序列化器**，非原文自动解析器（① 不读招标原文，计划书 §3.2 边界）。
- **`assets/outline.schema.json`（04 契约）**：计划书 §6.2 D4 字段集 `id/number/title/order/parent/depends_on/word_target/scoring_refs/status/notes`，`additionalProperties: false`，`id` 模式 `^n-[0-9a-f]{4}$`，`word_target` 注明"非金额、非页数"。
- **`build_04()` 按计划书 §6.2 重写**：父节点栈推导、`word_target` 按 chapter_id 聚合任务卡、`scoring_refs` 取 S-/T 前缀 source_ref；`schema_version` 0.2→0.1（③ SKILL.md 早已按 0.1 登记，实现才是漂移方；旧产物的 `style_source`/`typography` 属 01c 职责，04 不重复承载）。
- **`tests/check_01b_rawtext.py`（01b 引文逐行机检）**：raw_text 引文与招标原文比对（空白＋中英标点归一化后子串匹配；片段首尾须落原文边界，防无省略号静默截断；次级锚点允措辞差异如 UNIX→LINUX）；负向验证三种腐败形态（改数值/静默截断/锚点不存在）均被检出。

### Changed

- **01b 全量抽取第一批（P1-d）**：`SPEC_ITEMS` 2→16 行——新增第五章「发包人要求」2.性能指标（P3333–P3353）14 行（sp-003–sp-016）：可量化 8 行（覆盖验收基准 7 条：全场/单台可利用率 98%/96%、功率曲线 97%/95%、噪声日/夜 55/45dB、年等效小时数 2414h，另收强迫停机率 <5%）＋定性 6 行（主机考核/GB-DL/国产化/等保/智慧电站/调度数据网）；散文章节拆分口径「每个可独立核验的要求一行、并列保证值计多行」写入 docstring。sp-001 条款精确到「通用合同条款9.1.5」（P1356）、sp-002 照录前附表 1.3.3（T1R10）原文；`source.page_range` 与 docstring 如实登记"2.性能指标节已全量、**第五章其余 8 节挂起**，不得冒充全覆盖"。
- ① `SKILL.md`：frontmatter 0.4.0＋版本头行；§七 表更新为五件套脚本引用＋新增 `validate_plan` 行；生成说明段改写为五脚本结构。

### Fixed

- ① 5 个脚本 docstring 裸 `§` 引用（顿号后第二个跨文档引用丢前缀，scan_doc D2）补「计划书」前缀。

### Tests

- **`tests/test_stage1_regression.py` R4（5 项，累计 24/24 PASS）**：01b 引文机检逻辑固化——照录通过（省略号切片/次级锚点/表行锚点）；负例四项（改数值、无省略号截断、锚点不存在、id 重复）均检出。
- 验收项目（示例市）产物按新实现再生：01b 16 行过 schema；04 按 D4 字段集再生后 0 违约；②-A 重跑废标项 11（未响应 0）、资格项 7（未响应 0）、商务表 24/24。

## [bid-compliance-check/v0.3.0] - 2026-10-18

> ② references 七件落地＋跨章一致性骨架版（P1-b/c）：「判词库-投标侧」派生、七类检查细则文档化、`check_consistency.py` 独立实现（全套件唯一实现）。

### Added

- **`references/` 七件**：`判词库-投标侧.md`（派生自 ⓪ v1.5.0：六类扫描词＋第六类投标侧补充词——占位符清零/无偏差显式/禁照抄/模糊承诺/金额日期跨章一致/交叉引用；文件头注明派生来源与同步日期，**只取签章/暗标/废标词条不复制整份**）、`废标项比对方法.md`（A 类：主覆盖比对＋跨类否决级补充扫描＋孤儿卡四类成因）、`响应偏离表模板.md`（B 类：行来源 01b 逐行、禁照抄、正偏离须具体、no_negative_allowed=废标级）、`形式核对清单.md`（C 类）、`暗标匿名检查.md`（D10/D11：语境二分＋8 项终检）、`雷同自查清单.md`（计划书 §8.6：四道防线＋套话密度＋结构模板化＋独立性自查）、`资质时效核查.md`（F 类：四态判定＋换证窗口口径 3–6 个月未载明按 3 个月）。
- **`scripts/check_consistency.py`（②-B 骨架版）**：名称/编号精确基准比对全自动（purchaser 名先行置换再扫项目名变体；编号正则放宽"编号写成"一类无冒号形态；金额不收裸 4 位以上数字、工期不收"年"，防年份误报——R3-1 固化）；金额/日期/工期为信号扫描（纯文本不可判同语义）明示人工甄别，不假装定性；输出 `06_compliance/consistency-issues.md`（名称基准/编号基准/金额集合/日期集合/工期集合/G5 提示六节）；rc 0/2（stage≠writing 或无 05_chapters 拒跑）。
- ② `SKILL.md` §三 新增"检查类操作细则"索引表（七件 references＋②-A/②-B 脚本）；`README.md` 检查类节加七件明细表＋脚本清单。

### Changed

- `check_compliance.py` 偏离表齐全性行口径随 01b 抽取进度更新："01b 现有 N 条（2.性能指标节已全量 14 行，第五章其余 8 节挂起），逐行一致性以 01b 全量后重跑为准"。

### Tests

- **`tests/test_stage1_regression.py` R3（3 项）**：跨章一致性变体/异值检出且 purchaser 与年份不误报；负例 stage 非 writing 拒跑；负例无 05_chapters 拒跑。

## [repo/v1.6.0] - 2026-10-18

> 01b 全量第二批（3/5/6 节）的仓库级配套：验收记录续批小节、锁文件刷新至 ①=0.5.0／②=0.3.1。

### Changed

- `docs/v0.16_阶段1验收记录.md` 第六节增补「P1-d 续批」小节：新增 90 行（sp-017–106）按节明细、拆分口径 v2、机检证据（106 条引文机检一次通过/产物过 schema/回归 24/24/契约 PASS）；#1 更新为**部分通过（4/8 节）**——2.性能指标 14＋3.勘察设计 69＋5.调试验收 5＋6.施工工期 16 已逐行齐备，4/7/8/9 节挂起且段数/编号项数登记入档；#5 阻塞解除状态不变（基线扩至 106 条）。首批小节的 #1 表述同步注明"3/5/6 节已由续批解除"，避免新旧状态矛盾。
- `skills-lock.json` 刷新：①=0.5.0／②=0.3.1（`generated_at` 2026-10-18T16:44:34+08:00）；schema 清单无变化。
- `tests/check_01b_rawtext.py` 输出改按节汇总（第五章已全量 104 行＋跨章节 2 行，带比较符可量化 10）。

## [repo/v1.5.0] - 2026-10-18

> P1 四项收口的仓库级配套：回归测试扩容（R3/R4）、锁文件刷新、③ `knowledge.schema.yaml` 契约登记（③ 未升版）、验收记录追加 P1 执行结果节。

### Added

- **`tests/test_stage1_regression.py` R3＋R4（累计 24 项）**：R3 跨章一致性三项（②-B 骨架回归，含 purchaser/年份不误报负例）；R4 01b 引文机检逻辑五项（合成数据，自包含）。
- **`skills/bid-technical-proposal/assets/knowledge.schema.yaml`（③ 1 份单副本，不进 lock）**：02b 素材契约声明式定义（`id_pattern: ^kn-\d{3,}$`、五必填字段 `id/title/use_when/tags/verifiable_facts`），与 facts 分界、两级素材库；③ `SKILL.md` §六 契约表登记一行（阶段 1 契约）。
- **`tests/fixtures/02b_knowledge.sample.md`**：采用计划书 §6.3 原文示例节点 kn-012；`validate_contract.py` 新增 C5c 校验（frontmatter 解析＋required＋id_pattern＋tags 非空），负验证（id 改 `kn-01` 被拒后恢复）。
- **`tests/fixtures/04_outline.sample.json`**：8 节点从示例市真实产物提取（order 1/2/6/7/8/25/27/34、n-2102 word_target 29500 含 16 个 T4-\* scoring_refs、depends_on 如实为空），注册入 FIXTURE_MAP 过 C5。

### Changed

- `skills-lock.json` 经 `validate_contract.py --write-lock` 刷新：①=0.4.0／②=0.3.0、`outline.schema.json` hash 入锁；只校验模式复跑 PASS（C1/C2/C5/C10）。
- `docs/v0.16_阶段1验收记录.md` 追加「六、P1 执行结果」节（原第六节顺延为第七节）：P1-a/b/c/d 状态与机检证据；#1 转为部分通过（2.性能指标节 14 行 vs ≥7 基准，第五章其余 8 节挂起已如实自记）、#5 阻塞解除（01b 基线 16 条已备，完整验证仍待 writing 阶段）。历史判定不改写。

## [bid-response-plan/v0.3.0] - 2026-10-18

> ① 01c 章节树保真（阶段 1 验收 #2 根因修复）：技术标编号连续化重排 6 处 + 章节名删括号说明 3 处，改为按原文档真实序列固化 + 新增机检。

### Fixed

- **`build_bid_plan.py` `FORMAT_CHAPTERS` 技术标编号重排 6 处**：n-2103→"7"、n-2104→"8"、n-2105→"9"、n-2106→"10"、n-2107→"11"、n-2108→"12"（示例市原文档技术标编号自身即 1、2、7–12，"连续化"是转抄人造缺陷，验收记录 #2）。
- **章节名删括号说明 3 处**：恢复 n-2102「项目实施方案（由投标人自行编制）」、n-1131「施工分包情况表（适用于投标人不具备招标文件所要求的施工资质的情况）」、n-1132「设计分包情况表（适用于投标人不具备招标文件所要求的设计资质的情况）」。
- 同步更新全部引用点：TASKS（c-0012、bf-12、bf-13）、SCORING_DETAIL 16 行"项目实施方案"→全称、BUSINESS_FORMS bf-12/bf-13 第三列章名；模块 docstring 增补 🔴 保真规则三条（编号不拉直／括号不删／换项目必跑机检）。

### Added

- **`scripts/verify_format_chapters.py`（新建，保真机检）**：`--01c <01c_format-outline.json> --headings <第七章标题抽取.json>`，编号＋章节名与原文逐字比对；问题四分类——编号不存在（疑似连续化重排，附原文编号序列）／编号存在但名不符（改写或括号说明被删，附原文候选）／原文未收录／01c 内重复；rc 0/1/2；只报告差异，不自动修改。
- **`tests/fixtures/07_format_headings.sample-project.json`（新建，42 节点）**：由示例市第七章 P5398–P6161 逐行抽取并与原文交叉核对生成，技术标编号序列 `二、1、2、7、8、9、10、11、12` 如实记录，防 fixture 自身抄错。

### Tests

- **`tests/test_stage1_regression.py` R2（4 项）**：build_bid_plan 端到端生成（CID 全部可解析）→ verify 42 节点全过；负例一（历史缺陷形态 7→3＋删括号）检出"章节名不符＋括号说明被删＋原文节点未收录"；负例二（12→13 不存在编号）检出"疑似连续化重排＋原文编号序列"。
- ① `SKILL.md` 同步：frontmatter 0.3.0、主流程第 3 步卡点列扩为四项保真要求、§七 表更新 01c 行并新增机检行、尾部生成说明补机检命令与示例市案例。

## [repo/v1.4.2] - 2026-10-18

> 新增 `docs/v0.16_阶段1验收记录.md`（计划书 §11.2 阶段 1 合并验收正式记录，真实招标文件端到端实测），并追加换模型交叉验证（X 层）附录与内部一致性修订；无技能能力变更。

### Added

- **`docs/v0.16_阶段1验收记录.md`**：以真实工程类招标文件「示例发包人示例市 100MW 风电 EPC」为样本，对计划书 §11.2 阶段 1 验收 11 条逐条实测。
  - 结论：**不通过**（5 通过／3 不通过／2 不适用或延后／1 不可完整验证）。
  - 三条不通过：#0 评分分值闭合（根因为**契约缺口**——⓪ schema 无 `weight`／明示总分字段，加权型评分结构无法表达，D5 必然假失败）；#1 `01b` 逐行一致（仅 2 条且来源章节不符）；#2 `01c` 逐字一致（42 节点中 30 条名号全对，**6 处技术标编号重排**、3 处章节名删括号说明）。
  - 自审新发现缺陷 8 项（4.1–4.8）：`outline.schema.json`／`knowledge.schema.yaml` 缺失、F 类文案方向写反、⓪ 历史产物 63 处 schema 漂移，及 X 层合并纳入的 4 项（顶层缺 NOTICE、② references 缺 7 个含「接管」必建项 `判词库-投标侧.md`、①② 脚本结构不符且 `check_consistency.py` 未独立建、④ README 未完整覆盖计划书 §8.8.3）。
  - 机检与隔离声明：全部测试在 `workdir/acceptance/` 副本执行，用户工程目录只读；未修复任何产物后冒充通过；#7／#8／#9 前半／#5 的不可机检项均已如实标注。

### Added（X 层附录）

- **换模型交叉验证（X 层）结果与合并去重**：盲审工单 `workdir/cross-audit-2026-10-18.md`（1321 行自包含，含被审材料全文 + 12 项证据包，生成时经污染自检剔除 2 处真实自污染）投递另一模型回收，按「位置＋类型」合并去重：
  - **A 双源确认 1 项**（`outline.schema.json` 缺失，本方验收记录第四节已记录）；
  - **B 本方盲区、证据成立 4 项**（NOTICE／② references 7 个／脚本结构／④ README）；
  - **C 对方提到但不成立、已反驳 3 项**（LICENSE 实际存在且为 CC BY-NC 4.0；⓪ SKILL.md 已为 1.4.1，对方基于旧快照；阶段 1 验收已用真实招标文件端到端执行）；
  - **D 对方漏看 1 项**（② scripts 实际 2 个，`check_business.py` v0.2.2 新增未被计入）。
  - ⚠️ **投递偏差如实记载**：对方实际审的是「仓库结构 vs 计划书目录树」，未审本记录内部一致性——X 层对本记录结论的**独立复核尚未完成**，交付审查状态维持 ⚠️ SELF-ONLY，**未经该复核不得视为定稿**。

### Fixed（本记录内部一致性）

- 第四节缺陷由 4 项补全为 8 项（新增 4.5–4.8，与 X 层 B1–B4 对应）；第五节修复优先级表由 7 项扩充为 **10 项**（P0×2、P1×4、P2×4），并删除附录中重复的旧版优先级表；11 处裸 `§x.y` 引用补「计划书」前缀，过 `scan_doc` D2 跨文档引用校验。

### Notes

- 该记录初版曾直接打 tag `repo/v1.4.1` 而未补 CHANGELOG 条目，本条目一并补录；`repo/v1.4.1` 与 `repo/v1.4.2` 均为纯文档变更，无技能版本与锁文件变动。

## [repo/v1.4.0] - 2026-10-18

> 阶段 1 开发缺口补齐：`check_business.py`（M8 商务表专项检查）新建 + D5 评分表分值闭合验算脚本化。

### Added

- **`bid-compliance-check/scripts/check_business.py`（新建）**：M8 商务表专项检查，对应计划书 §11.2 阶段 1 验收第 9 条与计划书 §5 目录树。
  该文件此前被计划书 §5 点名、并被回归标记 M7（`regression_markers.json`）锁定 `must_contain: ["check_business.py"]`，**但仓库内从未实装**——属阶段 1 收口的真实缺口。检查项：
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
- 「表数＝招标格式章要求表数」（计划书 §11.2 #9 前半）在当前架构下**无法独立机检**：① 的 `BUSINESS_FORMS` 为硬编码常量（bf-01~bf-24，取自示例市项目第七章），② 不读招标原文、03c schema 亦无期望表数字段。已如实标注为「以 ① 抽取声明为准」，未伪造通过。

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

- v1.1.0：M 层机器自检（M1–M7，`scripts/scan_doc.py`）、X 层换模型交叉验证（盲审工单模板 `references/cross-audit-template.md`）、SELF-ONLY 四态输出、结构性变更后强制回扫（计划书 §7）
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
- **M7 schema 自述软化**：不再声称"与计划书 §6.2 唯一真源完全一致"，改为"与 v0.16 delta 定义一致（计划书 §6.2 回填待 v0.16 合并）"

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
