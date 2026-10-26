# Changelog

本仓库所有技能的版本变更记录。格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [SemVer](https://semver.org/lang/zh-CN/)。

Tag 约定：技能版本 tag 为 `技能名/vX.Y.Z`；仓库级变更 tag 为 `repo/vX.Y.Z`。

## [repo/v1.7.36] - 2026-10-26

> 交付双臂收口第三批（T1／T2／T3／T4／T6）：①②③ **入口闸门**（修复缺件时抛栈回溯）、②-B **暗标终检机检化**、`prompts/templates/` **十条模板填充**、v0.21 **核账报告**与**四份阶段验收记录**、计划书版本号收口，并修复 ⓪ 兜底版本常量漂移。版本：⓪ 1.5.1→**1.5.2**、① 0.22.0→**0.23.0**、② 0.5.1→**0.5.3**（③④ 不变）。

### Fixed

- **①② 入口闸门（原缺件时抛栈回溯，属产品级缺陷）**：`build_bid_plan.py` 新增 `gate()`、`check_compliance.py --mode A` 与 `check_business.py --mode A` 各新增 `gate_a()`，形态对齐 ④ `_common.gate()` 与本文件既有 `mode_b`——缺件／契约不符按「【执行阻断】→原因→缺少产物→处置」输出并 **rc=2 零产物**（此前抛 `FileNotFoundError`／`AssertionError` 栈回溯，虽同为非零退出但无产品级指路）。同时修正 ②-A／M8 **提前创建 `06_compliance/`** 的零产物破坏。
- **① stage 不符无指路**：现按 `references/流水线交接约定.md` L56–65 给出上游/下游技能归属（如 `plan_confirmed` → 「下一步是 ② bid-compliance-check，无需重跑 ①」）。
- **`02_facts` 口径统一**：按交接约定「可缺但须显式告警」，①② 均由「缺件阻断」改为 ⚠️ **不阻断**并明示 `blocked_by_facts`（此前 ②-A 误按缺件阻断，导致 T4-1e 失败，已修并固化）。
- **M8 重复验 stage**：`check_business.py` 不再自行验 stage，统一由 `check_compliance --mode A` 的 `gate_a()` 把关，避免同一关卡两处判定的口径漂移。
- **⓪ 兜底版本常量漂移**：`emit_facts.py` 的 `FALLBACK_SKILL_VERSION` 为 1.5.0（落后两个 patch），会在 SKILL.md 版本不可解析的回退路径写入过期版本号，进而被 ① 的新增 semver 比对误判为 minor 差异告警；已对齐并 bump ⓪ 至 1.5.2。

### Added

- **① `source_skill_version` semver 三档比对**：major 阻断／minor 告警／patch 静默（当前持仓产物 1.4.0 vs ⓪ v1.5.2 → 告警放行）；不可解析时提示而不阻断。
- **②-B 暗标终检机检化**（原「属 G5 人工项」）：`bid_mode=blind` 时以 `01c.typography.identity_ban` 为词条逐串扫 `05_chapters/*.md` 全文（去 YAML frontmatter），命中计 rc=1 并给出「文件名·行号」，早于 ④ 的 docx/PDF 层检查发现；清单为空仅提示补录不误伤（与 ④ `verify_docx` 同口径），`normal` 模式不启用。
- `prompts/templates/01-拆标.md` … `10-查一致.md`（**十条可直接改用的模板**，此前为 17 行索引占位）：每条按计划书第 8.8.1 节「五要素」（角色/任务/输入/约束/输出格式）成文，附「适用场景＋必填输入＋涉及铁律＋【能力依赖：L2】降级指令」；索引 README 改为带清单与使用须知（03 不得独立使用、04 必须过 G4 等）。
- `docs/审核报告_投标文件Skill建设计划v0.21_完成与未完成清单.md`：v0.21 全量核账——已完成七阶段明细、未完成 A（用户侧实测与盲审）／B（双母库零条目）／C（五项计划欠账）／D（部署同步已修复）／E（文档漂移）五类，附门禁 9 项机检证据与建议执行顺序。
- `docs/v0.21_阶段2验收记录.md` / `阶段3` / `阶段5` / `阶段6`：四份独立验收记录补齐（此前仅 CHANGELOG ＋ 回归，存在双轨漂移风险），均附本机实跑的回归项数与遗留。
- **测试固化**：阶段 4 回归由 44 项扩至 **60 项**——新增 T4-8（入口闸门，十二项：空目录阻断无栈回溯、零产物、stage 指路、缺件逐条列出、`02_facts` 告警不阻断）与 T4-9（②-B 暗标机检，四项：命中 rc=1、写入报告留痕、清单空不误伤、`normal` 不启用）。

### Changed

- 计划书 `docs/投标文件Skill建设计划_v0.21.md`：§5 目录树 ⓪ 版本、§6.2 `skill_versions` 示例、附录 C 版本钉死行，由过期快照（⓪ v1.4.1／① 0.2.0／② 0.2.2／③ 0.1.1／④ 0.1.1）刷新为 2026-10-26 实读值并注明复核日期；历史叙事句保留原文，仅追加复核注。
- ② SKILL.md 能力表：删除「暗标终检属 G5 人工项」的过期表述，改为「已机检化 ＋ 文本层外仍须人工抽检」。
- `docs/审核报告_投标文件Skill建设计划v0.21_完成与未完成清单.md` **提交前订正**（原文主体成稿于当日 11:21，此后并行会话与本轮施工使三处结论失准）：素材母库由「0 条」订正为「54 条」（`knowledge/` 于 12:08 后由并行会话完成首填充，`check_knowledge` 仍 PASS）；C2 十条模板与 C4 暗标机检化标记为「已于本轮交付」并删除线保留原项号；六阶段回归总数由 277 订正为 **281**（实跑 32＋73＋74＋60＋28＋14）。另订正一处乱码句（「⑤CD 场景」→「缺产物场景」）。

## [repo/v1.7.38] - 2026-10-26

> **推送前统一脱敏**（用户 2026-10-26 决策）：本仓库对外公开，此前会话把真实招标项目的身份信息写进了提交，部分已推送到远端。本轮对全仓做去标识处理，并随后重写本地全部历史再 force push。技能功能零变更，六阶段回归 281 项仍全绿。

### Changed

- **项目身份去标识**：业主/单位名→`示例发包人`，属地→`示例市`／`某市`，乡镇村名→`甲村乡`／`乙村乡`，场址经纬度→`NN.NNN` 一类占位，招标编号→`ZB-DEMO-2026-00X`，暂定价金额→`若干金额（已脱敏）`。累计替换约 300 处、涉及 36 个文件；技术形态学证据（如 100MW 风电 EPC 的章节构成、编号跳号形态）全部保留，测试断言一个未破。
- **13 份真实招标样本代号化**：文档中原本实名列举 13 份真实标书（业主＋地名＋容量的组合），统一改为 `P01–P13`，形态学证据保留、主体不可反推。
- **本机绝对路径占位符化**：盘符路径与 Windows 用户名一律改为 `<本机工作区>`／`<受控项目根>`／`%USERPROFILE%` 等占位符；含早期会话因转义失误产生的双斜杠变体（如 `<企业事实母库>/`）一并清理。命令行示例仍可照读执行。
- **两个受污染文件名改名**：格式章标题 fixture 改为 `07_format_headings.sample-project.json`、机器链试跑记录改为 `2026-10-21_machine-chain.md`，引用点同步更新（回归实测通过）。
- **派生二进制移出仓库**：`docs/` 下由 md 报告导出的 `.docx`（866 KB，二进制无法做文本脱敏，且与同名 `.md` 内容重复）停止跟踪，文件留本机；`.gitignore` 新增 `docs/*.docx` 防复发。
- `tools/run_all_checks.sh`：阶段 4 回归标注由过时的「44 项」更正为实跑值「60 项」。
- `AGENTS.md`：新增「提交内容禁止出现真实项目信息」条目，列明代号约定与三条连带约束（测试夹具须同步用代号、替换词表本身不得入库、派生 docx 不入库），并写明敏感信息一旦入提交必须重写历史。

### Removed

- 上述 `.docx` 派生稿从版本控制移除（本机保留，需要时由同名 `.md` 重新导出）。

## [repo/v1.7.37] - 2026-10-26

> 本机数据留存策略：**素材条目与企业事实库不进 GitHub**（用户 2026-10-26 决策，与此前「企业事实母库放本地不入仓库」的既定决策一致）。技能内容零变更。

### Changed

- `.gitignore` 新增两条排除规则：`knowledge/**/kn-*.md`（具体素材条目）与 `企业事实库/`（兜底；该库默认在 `<企业事实母库>/`，含证书号/合同额/人员证号等高敏感数据）。**仍入库**：`knowledge/` 下的 README、各类别 README、`入库规范.md`、`tags词表.md`、`素材条目模板.md`（结构与规范；已机检确认无敏感值）。
- `knowledge/tags词表.md`：增补业态标签「海上风电」「房建」，`风电` 一档补注「默认陆上」（遵循该文件「新增标签先改本表、再入库条目」的约定；词表属公有结构，随仓库公开）。
- `AGENTS.md`：新增「素材条目与企业事实库本机留存、不进 GitHub」踩坑条目，明确**禁止 `git add -A` 一把梭**（2026-10-26 曾误提交 54 条素材条目，该笔已从本地历史摘除，未推送）。
- 核账报告 v0.21：B 类两行补注「本机留存、不入库」。

### Removed

- 从本地历史摘除「knowledge 素材母库首填充」一笔（54 条目 ＋ 词表）：该笔仅存在于本地、从未推送；条目内容保留在磁盘 `knowledge/` 下，仅供本机 `check_knowledge.py` 与后续填充使用。

## [repo/v1.7.35] - 2026-10-26

> 交付双臂收口第一、二件事（依据 2026-10-26 对本轮开发任务完成度审核的建议序）：① 修复 WorkBuddy 运行目录装载滞后；② 备齐 D1/D2/D3 三张平台实测卡的执行前置（含 D2 场景物料与机制侧干跑）。技能内容零变更，五技能版本不变（⓪ 1.5.1／① 0.22.0／② 0.5.1／③ 0.3.1／④ 0.2.2），故 `skills-lock.json` 无需刷新。

### Fixed

- **WorkBuddy 运行目录同步**（此前装载旧版，属漏同步）：`%USERPROFILE%\.workbuddy\skills\` 下 ①②③④ 由 ① 0.6.0／② 0.3.3／③ 0.1.1／④ 0.1.1 同步为 **① 0.22.0／② 0.5.1／③ 0.3.1／④ 0.2.2**（⓪ 1.5.1 本已一致），①②③ 补入 `SKILL.lite.md`（④ 按计划书 §9 不做 lite）；同步后逐文件 SHA256 比对，**缺文件 0、哈希差异 0**（排除 `__pycache__`），文件数 7/26/18/16/22 全等。
- **清理旧版嵌套残留**：`bid-response-plan`、`bid-compliance-check`、`bid-docx-export` 三个技能包内存在的同名嵌套副本（① 0.6.0／② 0.3.2／④ 0.1.1，共 54 文件）已**移出**（非删除）至 `<同步备份目录>\_nested_removed\`。

### Added

- `evals/trigger-tests/执行准备与前置验证_2026-10-26.md`：三张实测卡的执行前置记录——§1 运行目录同步前后版本对照与哈希校验结果；§2 五技能 description 静态路由分析（长度 214–287 字符，首 40 字均含区分词，缓解已知 40 字截断风险）；§3 D2 四场景物料说明与机制侧干跑实录；§4 待用户执行的 17 场景清单与回填路径。
- `workdir/acceptance/d1d2/`（gitignore）：D2 拒约场景物料四套——`D2-1_空目录`、`D2-2_残缺01`（故意去掉 `contract_schema_version`/`scoring` 的 01）、`D2-3_仅01系列`（stage=planning 无 03/04/05）、`D2-4_有报告未处置`（stage=checking 未过 G3），各含 `场景说明.md`（目的/开场白/预期行为）。

### Changed

- `evals/trigger-tests/D1-D2-平台触发与拒绝测试卡.md`、`D3-L0轻量版平台实测卡.md`：头部加 2026-10-26 指引——明确"同步前的实测结果对当前版本无效"、指向执行准备文件与 D2 物料目录，并标注卡内旧版本快照已过时。
- `AGENTS.md`：「容易踩的坑」新增两条——运行目录已同步（含"两个装载目录都要同步"的教训）；①② 脚本缺入口闸门（P2 未施工，记录现象与建议）。

### Evidence

- 同步后校验：PowerShell 逐文件 `Get-FileHash SHA256`（源 vs 目标，排除 `__pycache__`）→ 五个技能 diff=0，无 MISSING IN SRC；`grep '^version:'` 实读五个 SKILL.md → ⓪ 1.5.1／① 0.22.0／② 0.5.1／③ 0.3.1／④ 0.2.2。
- 备份：`<同步备份目录>\`（原运行目录 110 文件 + `_nested_removed\` 54 文件），可整目录回滚。
- D2 四场景干跑（2026-10-26 实跑）：D2-1 `build_bid_plan.py` rc=1（⚠️ traceback，零产物）；D2-2 `check_compliance.py --mode A` rc=1（⚠️ traceback，中文异常消息）；D2-3 `export_docx.py` rc=2（✅ 逐条缺件清单 + 阻断导出，零产物）；D2-4 无脚本入口（③ 写正文由 SKILL.md 五步循环 + stage 门控制，非脚本）。
- 门禁：`bash tools/run_all_checks.sh` → 通过 9 项 / 失败 0 项（技能内容零变更，`skills-lock.json` 无漂移）。

### 未完（本次不做）

- D1（8 句）/D2（4 场景）/D3（5 场景）平台观测与回填——**必须由用户在真实平台新会话执行**，AI 无法自触发观测。
- X 层套件设计级盲审工单投递与合并（`evals/cross-audit/盲审工单-套件设计-2026-10.md`）——未合并前阶段 4 不关闭、交付上限 ⚠️ SELF-ONLY。
- ①② 入口闸门（P2 建议，待用户裁定优先级）。

## [repo/v1.7.34] - 2026-10-22

> 工程卫生收口（评审意见整改第二优先组）：README 版本表与 frontmatter 实值同步、补充一键校验与最小 CI、收敛 quantity-takeoff 超额声明。依据用户 2026-10-22 批准的执行三件事。

### Changed

- `README.md`：技能一览表 7 行版本号全部对齐 frontmatter 实值（⓪ v1.5.1／合同 v1.1.0／审查 v1.1.3／① v0.22.0／② v0.5.1／③ v0.3.1／④ v0.2.2），同步更新各技能定位一句话描述；补 `.gitignore` 忽略规则（`.dumate/`、`.opcteam/`、`tmp/`、根目录两份对比报告 docx）。
- `quantity-takeoff-building/SKILL.md`（仓库外备份副本）：将「通用房建工程量计算」超额声明收敛为实际能力——**当前实现＝混凝土/钢筋/依附几何模板三类**；适用边界表增加「❌ 未覆盖」行（土方/砌筑/装饰/机电等为愿景分层），description/触发词同步去掉未实现专业的承诺（土方量、装饰工程量）。

### Added

- `tools/run_all_checks.sh`：一键校验入口——契约闸门 validate_contract（C1–C13）＋ 阶段 1~6 回归（265 项）＋ check_knowledge（K1–K9）＋ 计划书 scan_doc（D1–D6，文件存在时跑）＋ 企业事实母库 check_facts_library（设 `FACTS_LIB` 时跑，本机专用不入 CI）；单检查失败 rc=1 并保留首个失败日志片段，全部通过 rc=0。
- `.github/workflows/ci.yml`：最小 CI——push/PR 跑契约闸门＋阶段 1~6 回归＋check_knowledge（零三方依赖，Python 3.11），并用 `git diff --exit-code` 验证校验不改动 `skills-lock.json`（防止 lock 漂移）。

### Evidence

- `bash tools/run_all_checks.sh`：通过 9 项 / 失败 0 项（validate＋s1~s6＋check_knowledge＋scan_doc 全绿；check_facts_library 按设计 SKIP，本机专用）。
- 版本同步依据：逐个读取 `skills/*/SKILL.md` frontmatter（name/version/description）核对，7 技能实值与 README 表一致；`skills-lock.json` 既有五技能版本与 hash 不受影响。

## [repo/v1.7.33] - 2026-10-21

> 企业事实母库落地（**本地私有，不入仓库**）＋ `tools/select_facts.py` 快照链（计划书 v0.21）。依据用户 2026-10-21 二次拍板（翻转同日早前「留待将来」口径）：企业资质等可核查事实**要跨项目复用**；母库放本地（证书编号/合同额/人员证号高敏感，仓库推 GitHub）；项目快照走确定性拷贝。「材料归集」技能仍不建（前次拍板不变）。

### Added

- `<企业事实母库>\`（仓库外本地目录）：README 入库规范（红线三条——永不入 git/不外传、AI 只读不写〔facts.schema.yaml R5〕、逐字引用；两级库语义与 `knowledge/` 同构；录入流＝agent 起草→用户逐项确认→落库，不 OCR〔R3〕；id 只增不回收，换证=新条目新 id）＋ `模板.md`（五类条目示例）＋ 五节空 yaml（qualifications/performances/personnel/equipment/financials，结构先行，暂无条目）。
- `tests/check_facts_library.py`：L1–L8 母库机检——五节文件在位＋根级无野文件／单节结构（顶层标量拒绝）／id 前缀与跨文件唯一／必填字段（节字段＋公共 source/updated_at/owner）／**母库禁录 is_decisive·evidence_ref**（项目语境字段，机检 L5）／日期格式／R2 aging（超 12 个月 W 级）／数值与布尔类型；空库绿、违约 rc=1；零三方依赖；`--library` 必填参数（母库路径机器本地化）。
- `tools/select_facts.py`：母库 → `<项目>/bid/02_facts.yaml` 确定性快照——`--ids`/`--sections`/`--all` 选择（可并集）；逐字拷贝字段值（额外字段原样保留）；`is_decisive` 统一注入 false＋头注释双复核位（G2 逐条按本项目资格条款复核；evidence_ref 待 ④ 索引后人工关联）；**已存在快照拒绝覆盖**（保护项目侧人工增补），`--force` 自动备份 `02_facts.yaml.bak-<时间戳>`；选择集空报错不产出；PyYAML 可用时完整解析、缺失时零依赖极简解析（与 ② 口径一致）。
- `tests/test_stage6_regression.py`：T6-1~T6-7 共 14 项永久回归（快照正向＋schema_version＋双复核位头／PyYAML 回读类型值保真〔含额外字段保留〕／未知 id rc=1 不产出／覆盖拒绝＋`--force` 备份重写／`--all` 全量／checker 合成库 PASS＋目录缺失 rc=2／checker 负例 10 类自证＋aging W 级）。

### Changed

- `docs/投标文件Skill建设计划_v0.20.md` → **v0.21**（改名＋§0.0 登记，旧 0.0.x 顺延至 0.0.7）：§5 目录树增 `tools/` 行＋02_facts 行注记；§6.3 新增两级事实库表（母库=仓库外本地、快照=项目 02_facts.yaml）；§11 阶段表第 6 行增补；新增 §11.8 企业事实母库结构验收；R2 处置列补落地注记；新增 R20（企业敏感数据误入公开仓库——母库置于仓库外＋仓库只承载无数据工具）。
- `AGENTS.md`：必跑命令增 `test_stage6_regression.py`（14 项）与 `check_facts_library.py`（带本机路径注记）；"容易踩的坑"与"当前施工前沿"更新。

### Evidence

- `python tests/check_facts_library.py --library <企业事实母库>`：空库 PASS（0 条目，五节全识别）；
- 负例探针（临时树，跑毕即删）：未知文件/缺 issuer/坏日期/id 形态非法/前缀错文件/id 重复/禁录 is_decisive/顶层标量/非本文件节键/amount 非数值/缺 source 共 12 项错误全命中 rc=1，aging W 级命中，缺失目录 rc=2；
- `python tools/select_facts.py` 冒烟 26 项（含 PyYAML 回读）全过；
- `python tests/test_stage6_regression.py`：14 项全绿；
- `python tests/scan_doc.py docs/投标文件Skill建设计划_v0.21.md`：D1–D6 全过（表格 61 张）；
- 门禁十件全绿：validate（C1–C13）＋s1 32＋s2 73＋s3 74＋s4 44＋s5 28＋s6 14＋scan_doc v0.21＋check_knowledge（空库）＋check_facts_library（空库）。

## [repo/v1.7.32] - 2026-10-21

> 素材母库（`knowledge/`）结构落成——阶段 6 重定义（计划书 v0.20）：**结构先行、内容按业态持续补充、领域中立**。依据用户 2026-10-21 拍板，消除原"新能源垂直库"与"工程类通用"定位的领域绑定矛盾（新能源降级为 tags 词表业态维度之一）。

### Added

- `knowledge/` 骨架：5 类别目录（`01-同类工程经验`／`02-专项工艺`／`03-保证措施`／`04-服务承诺`／`05-技术路线`，各附类别说明 README）——按素材类别分层、业态/地区/环节走 tags，不按业态分目录（避免通用素材复制两份）。
- `knowledge/README.md` 入库规范：素材/事实分界、两级库快照语义（③ 永不直读母库）、拆条粒度（一组 use_when＋一个做法单元，300–800 字）、**敏感信息与事实清洗红线**（可核查事实不留正文——抽 `verifiable_facts` 引用或删除；历史标书整段搬运前必须清洗）、母库附加三字段（source/updated_at/owner，README 约定层**不动 ③ 契约**——`knowledge.schema.yaml` 0.1 零变更，③ 校验 02b 只认五字段、多余字段无害兼容）、id 编号规则（`kn-XXX` 只增不回收，文件名前缀=id）。
- `knowledge/tags词表.md` 受控词表 v1：四维（业态/环节/地区条件/章节场景）29 个唯一标签（32 行，「通用」四维复用）＋「通用」承载跨业态素材；**词表外红灯，增补先改词表再入库**（同一次提交，防"风电/风力发电"式漂移）。
- `knowledge/素材条目模板.md`：frontmatter 八字段样例＋入库前自检三问（事实清洗/tags 词表/source 可追溯）。
- `tests/check_knowledge.py`：K1–K9 机检——目录结构（5 类别目录＋根级无野文件）／契约五字段＋附加三字段／id 唯一性／tags 词表命中／日期格式与 aging（超 12 个月 W 级提示，R8）／事实 id 形态／正文非空／文件名-id 一致；**空库绿、违约 rc=1**；零三方依赖（Python ≥ 3.8）；支持位置参数指定 knowledge 根（默认仓库根）。

### Changed

- `docs/投标文件Skill建设计划_v0.19.md` → **v0.20**（改名＋§0.0 登记，旧 0.0.x 顺延至 0.0.6）：§5 目录树 `knowledge/` 行更新（"待建"→结构落成）；§11 阶段表第 6 行重定义（素材母库结构先行）；新增 §11.7 阶段 6 结构验收（结构中立/红线成文/词表 v1/机检 K1–K9/空库期 ③ 行为不变/条目内容不交付）；R8 处置列补落地注记。
- `AGENTS.md`：必跑命令增 `check_knowledge.py`（八件套→**九件套**）；"容易踩的坑"与"当前施工前沿"更新。

### Evidence

- `python tests/check_knowledge.py`：空库 PASS（0 条目；结构 5 目录＋词表 29 标签全识别）；
- 负例探针（临时树，跑毕即删）：根级野文件/缺字段 owner/id 重复/词表外标签/事实 id 形态非法/文件名-id 不符/aging＋空壳 7 类全命中，正例树单独跑 rc=0；
- `python tests/scan_doc.py docs/投标文件Skill建设计划_v0.20.md`：D1–D6 全过（表格 60 张）；
- 门禁九件全绿：validate（C1–C13）＋s1 32＋s2 73＋s3 74＋s4 44＋s5 28＋scan_doc v0.20＋check_knowledge（空库）。

## [repo/v1.7.31] - 2026-10-21

> 专家复核批次 1–4 修复：两份专家审核报告（《复核结论_20261021》＋《审核报告_投标文件Skill建设计划v0.16_成果逻辑与遗漏复审》）实锤缺陷按批次执行——批次 1（代码 P0/P1：C1/C4/C5/C6/C8/C12/D3/D4/F1/F2/F4/F5/F7/F8/F12/F14/F16b）＋批次 2（断言 s2 +9/s3 +12）＋批次 3+4（文档口径统一：F10/F11/F15/F16/F17/③入口计数/④契约表 03 版本）。批次 4 两项按口径 A：F10 声明对齐（附件引用去空格）、C4 日期一致性入 rc。计划书升 v0.19。

### Fixed（批次 1 · ② `bid-compliance-check` → v0.5.1）

- `check_consistency.py`：**C1** 金额同值异形死条件（`n_norm` 按"可归一写法数"计，全部写法可归一且归一同值才放行，混归一仍报 ⚠️）；**C4** 关键日期槽 `group_date_slots`（截止/开标/递交/有效期四槽，槽词后 40 字内取日期，同槽多值 ⚠️ 抬 rc=1；排期类日期仍信号不判）。
- `check_compliance.py`：**C5** `qual_timing` 返回三元组（整体最坏态/明细/结构化 items），`compliance-report.json` 的 `f_qual_timing = {status, items, required_facts, deadline, detail}`；**C6** `_fm_status` 解析 frontmatter，mode B 对 draft 章警告（报告＋stdout，不阻断）；**C12** mode B 前置缺章阻断（04_outline 节点 vs 05_chapters 文件，rc=2）。
- `check_business.py`：**C8** `--mode B` 实装 `mode_b_business()`——08_business 行内「中文大写 vs 数字金额」等值核对（归一比对，不等值 rc=1；分项合计=总价声明人工）；退出码透传 `sys.exit(main())`。

### Fixed（批次 1 · ③ `bid-technical-proposal` → v0.3.1）

- `word_count.py`：**C12** MISSING 章节/孤儿文件从信息态抬 rc=1。

### Fixed（批次 1 · ④ `bid-docx-export` → v0.2.2）

- `_common.py`：`gate()` 重写——**C5** 读侧兼容 `f_qual_timing` dict/list 双形态，expired 由 warn 放行改 **fail 阻断**（解析失败亦阻断）；**C6** `status≠final` 章阻断；**C12** 缺章（01c 节点 vs 05_chapters 文件）阻断；**D3** `style_source` 缺失 warn/不一致 fail；**F12** `check_skill_lock()` 运行时自检（向上 ≤3 级找 skills-lock.json，不对齐 warn 不阻断）＋ `CHAPTER_FILE_RE`/`read_skill_version`；`replace_ev`/`parse_style_yaml` 共享化。
- `export_docx.py`：**F1** 标题剥离 ##/5/4/3/2 递归；**F4** `PN_MODES` 页码四档（none/header_center/footer_center/footer_outer），CT/DOC_RELS/部件按档位动态组装（footer_outer 加 evenAndOddHeaders）。
- `assemble_pdf.py`：**F2** `[[EV:]]` 替换收敛循环（≤3 轮：替换→重排→ev_map 稳定），`pagination.json` 记 `page_number_mode/ev_replaced/ev_converged`；**F1** 标题剥离与 docx 口径一致；**F4** `build_pdf(page_streams, pn_mode, margins)`。
- `verify_docx.py`：**F8** 入口上 gate；**F14** 中英文空格检查反转（扫「误加空格」对齐计划书 §8.7 规则 2，信息态）；**F7** 暗标标识扫描并入 PDF 文本层（`_common.pdf_identity_hits`：zlib 解压流＋UTF-8/UTF-16＋UCS2-BE hex）；通过分支 stdout 打印信息态警告（藏报告易漏看）。
- `scrub_metadata.py`：**F8** 入口上 gate；blind 段 PDF 文本层扫描（与 verify 共用）。
- `build_style_profile.py`：**F5** 字体白名单外照录＋警告（不回落不阻断）；**D3** main 写回 `00_metadata.style_source`；**F16b** `BASELINE` 单源化——载自 `assets/style-profiles/通用中文基线.yaml`（行尾注释剥离＋类型归一），缺失/不可解析即阻断不回落硬编码。
- `check_evidence.py`/`index_evidence.py`：**D4** 证据 `valid_to` 全空/部分空警告。

### Changed（批次 2 · 断言）

- `tests/test_stage2_regression.py`：新增 **T2-11 系列 9 项**（截止槽两值 ⚠️/同槽同值不报/金额混归一组 ⚠️/draft 警告不阻断/mode B 缺章 rc=2/`qual_timing` 三元组契约/商务行内大小写等值与不等值/08_business 空目录 rc=2）；T2-8a/T2-8h 随 ③ 升版断言 0.3.1。
- `tests/test_stage3_regression.py`：新增 **T3-12 系列 12 项**（④ gate 负例：expired dict/list 双形态阻断、draft 章阻断、缺章阻断、lock 对齐静默/漂移警告、中英文加空格检出、PDF 文本层扫描命中、页码档 none/header_center/footer_outer 三档部件、字体白名单外照录警告）＋**T3-11f** 基线单源断言（BASELINE 载自 yaml 逐键一致）；mkbid 的 03 版本 0.3→0.2（镜像 bid-plan.schema 冻结值）；T3-10b/T3-11a/T3-11e 随 ④ 升版断言 0.2.2。
- `tests/test_stage4_regression.py`：T4-1v 随 ④ 升版断言 0.2.2。

### Changed（批次 3+4 · 文档口径统一）

- `skills/bid-docx-export/SKILL.md`＋`references/样式与编号规范.md`＋`references/证明材料装配规则.md`：**F10** 附件引用口径统一「见附件A-xx（第 N–M 页）」（附件号与「（」之间不加空格，4 处）；**F11** 档位判定声明对齐代码口径（`01c.typography.source == tender_required` 为准，① 抽取规则保证同步）；契约表 03_bid-plan 版本 0.3→**0.2**（镜像 schema 冻结值）。
- `skills/bid-technical-proposal/SKILL.md`：入口校验「四步」→「五步」（计数实锤）；去「骨架版」陈旧措辞（check_consistency 已 v0.4.0 实装）。
- `tests/scan_doc.py`：**F17** docstring 去硬编码版本号（改「取版本号最大的一份」）。
- `docs/投标文件Skill建设计划_v0.19.md`（由 v0.18 升版改名）：**F15** §5 目录树补 ① 2 件（build_bid_plan/verify_format_chapters）＋④ 3 件（export_docx/_common/pdfutil）；**F16** style-profiles 实况 3 件（README/通用中文基线/暗标叠加层）＋运行期生成注明（招标规定/甲方模板两档不落 assets）；§0.0 登记本版变更（旧 0.0.x 顺延至 0.0.5）。
- ②③④ SKILL.md frontmatter bump（0.5.1/0.3.1/0.2.2）＋版本历史行＋§七 标题＋README 版本节；② §七 能力表三行更新（F 资质时效三元组契约/A-lite draft 与缺章/C 跨章日期槽与死条件/M8 mode B）。
- `AGENTS.md`：必跑命令补 `test_stage5_regression.py`（28 项）与计划书 v0.19；s2/s3 计数刷新。

### Evidence

- 门禁八件全绿：validate（C1–C13，`--write-lock` 后）＋ s1 32/32＋s2 **73/73**＋s3 **74/74**＋s4 44/44＋s5 28/28＋`scan_doc docs/投标文件Skill建设计划_v0.19.md` D1–D6（表格 60 张）。
- ④ gate 负例全部实测阻断（T3-12a/a2/b/c）；页码四档 docx 部件实测（T3-12g/h/i）；PDF 文本层命中实测（T3-12f，BodyWriter UCS2-BE hex 载体）。
- 修复期教训两条入档：①`pdf_identity_hits` 迁移时 edit 截断未复核导致 s3 两败（T3-9c/10c），`_common` 落盘复核后恢复；②基线 yaml 行尾注释致 `parse_style_yaml` 类型解析失败，`_load_baseline` 剥注释后通过。

## [bid-compliance-check/v0.5.1] - 2026-10-21

> 专家复核批次 1：② 侧代码修复（C1/C4/C5/C6/C8/C12）。详见 repo/v1.7.31。

### Fixed

- `check_consistency.py`：C1 金额同值异形死条件（`n_norm` 可归一写法数）；C4 关键日期槽（截止/开标/递交/有效期同槽多值 ⚠️ 抬 rc=1）。
- `check_compliance.py`：C5 `qual_timing` 三元组＋`f_qual_timing` 新契约（status/items/required_facts/deadline/detail）；C6 draft 章警告不阻断；C12 mode B 前置缺章阻断 rc=2。
- `check_business.py`：C8 `--mode B` 行内大小写金额等值核对（不等值 rc=1）＋退出码透传。

## [bid-technical-proposal/v0.3.1] - 2026-10-21

> 专家复核批次 1/3：word_count rc 语义＋文档口径。详见 repo/v1.7.31。

### Fixed

- `word_count.py`：MISSING/孤儿抬 rc=1。
- `SKILL.md`：入口校验计数「五步」；去「骨架版」措辞；check_consistency 能力引用更新 v0.4.0。

## [bid-docx-export/v0.2.2] - 2026-10-21

> 专家复核批次 1：④ 导出链防线补强（gate 阻断/PDF 文本层/页码四档/EV 收敛/基线单源等 14 项）。详见 repo/v1.7.31。

### Fixed

- `_common.py`：gate 重写（expired 联动阻断/缺章/draft 章/style_source/F12 lock 自检）＋`pdf_identity_hits`＋`parse_style_yaml`。
- `export_docx.py`：F1 标题剥离；F4 页码四档部件动态组装。
- `assemble_pdf.py`：F2 EV 替换收敛循环；F4 build_pdf 页码档。
- `verify_docx.py`：F8 入口 gate；F14 空格方向反转；F7 PDF 文本层扫描；信息态警告 stdout 可见。
- `scrub_metadata.py`：F8 入口 gate；blind 段 PDF 文本层扫描。
- `build_style_profile.py`：F5 字体白名单警告；D3 style_source 写回；F16b 基线单源载入。
- `check_evidence.py`/`index_evidence.py`：D4 valid_to 空值警告。

## [repo/v1.7.30] - 2026-10-21

> 阶段 5 交付（计划书 §9／§11.6）：多平台轻量版 `SKILL.lite.md` ①②③ 三份落地（P2），L0 纯对话平台（豆包、搭子等）可独立跑通"策划 → 合规自检 → 单章生成"三步。配套 `validate_contract` C13 契约检查、`test_stage5_regression.py` 28 项、计划书升 v0.18、D3 实测卡。

### Added

- `skills/{bid-response-plan,bid-compliance-check,bid-technical-proposal}/SKILL.lite.md`（88/91/86 行，随 ① v0.22.0／② v0.5.0／③ v0.3.0 交付）：L0 纯对话版自包含提示词——触发边界与拒绝路径（缺上游产物指回上游技能）、四层降级表（L0–L3）、每步末尾【能力依赖：L2】＋降级指令（各 4 处）、铁律自包含（IRONLAWS 块与主文件逐字一致）、R7 状态快照（无文件系统平台的对话内状态卡，回贴续做）；② lite 承载"任务卡覆盖＋F 类时效三态走查"（§9 定义 L0 价值最高的一步）；③ lite 强制"一章一轮"。
- `tests/test_stage5_regression.py`：T5-1~T5-8 共 28 项永久回归（lite 在位/形态/铁律一致/L2 标注/拒绝路径/状态快照＋C13 检测器六负例自证〔缺 lite、frontmatter、铁律漂移、L2 不足、④ 前向兼容〕＋validate 全绿）。
- `evals/trigger-tests/D3-L0轻量版平台实测卡.md`：5 场景用户实测卡（① 四步停 G1／① 无清单拒绝／② 覆盖+三态／③ 无素材停 G4／③ 成文带标注＋快照），待用户执行回填。
- `docs/投标文件Skill建设计划_v0.18.md`（由 v0.17 升版改名）：①§0.0 登记本版变更（旧 0.0.x 顺延）；②§5 目录树 ①②③ 三行补 `SKILL.lite.md` 标注；③§9 硬性要求段后补交付登记句；④§11 新增 **11.6 阶段 5 验收** 小节（六条：三份在位/§9 硬性要求闭合/无路由冲突/铁律防漂移/C13 自证/D3 待用户）。设计正文、铁律、schema 契约零变更。

### Changed

- `tests/validate_contract.py`：新增 **C13**（SKILL.lite.md 契约——①②③ 三份必在位〔④⓪ 不强制但存在即校验〕；无 frontmatter 防平台误加载为独立技能造成路由冲突；IRONLAWS 与主 SKILL.md 逐字一致防两处漂移；≥3 处【能力依赖：L2】标注）；docstring 校验项列表同步。
- `tests/test_stage2_regression.py`：T2-8a 断言随 ③ 升版改 0.3.0（名称标注"阶段 5 升版：lite 新增"）。
- ①②③ SKILL.md：frontmatter version bump＋版本历史行追加 v0.22.0/v0.5.0/v0.3.0 记录＋§七 能力表各增 lite 行（① 的 §七 标题陈旧版本号 v0.2.0 一并修正为 v0.22.0）；README 版本节同步并补"轻量版"依赖行。
- `skills-lock.json`：--write-lock 刷新（① 0.22.0／② 0.5.0／③ 0.3.0；lite 不入锁——版本随主技能）。

### Evidence

- 门禁七件套全绿：validate（C1–C13 含新增）＋ s1 32/32＋s2 64/64＋s3 61/61＋s4 44/44＋**s5 28/28**＋`scan_doc docs/投标文件Skill建设计划_v0.18.md` D1–D6 通过（表格 60 张）。
- C13 检测器负例自证：缺 lite／带 frontmatter／铁律漂移／L2 标注不足（2 处）／④ lite 铁律不一致，五种负例全部抓出（T5-7b~f），正例零误报（T5-7a）。
- lite 与主文件铁律逐字一致经三份独立比对（T5-3）；① README 版本行含 0.22.0（原 0.2.0 陈旧值一并修正）。

## [bid-response-plan/v0.22.0] - 2026-10-21

> 阶段 5：新增 `SKILL.lite.md`（L0 纯对话版轻量提示词，计划书 §9）。脚本与机读产物零变化。

### Added

- `SKILL.lite.md`（88 行）：触发边界（缺 ⓪ 七类清单即拒）／四步流程（入口校验与 G2 → 任务卡表〔每项一行＋response_form＋p-0001 补遗前置〕 → 目录骨架〔章名逐字〕 → 缺口清单＋停 G1）每步末尾【能力依赖：L2】＋降级指令；铁律自包含；R7 状态快照。

## [bid-compliance-check/v0.5.0] - 2026-10-21

> 阶段 5：新增 `SKILL.lite.md`（L0 纯对话版轻量提示词，计划书 §9——"纯提示词走查：检查任务卡覆盖、F 类时效三态，不依赖正文质量，恰是 L0 价值最高的一步"）。脚本与机读产物零变化。

### Added

- `SKILL.lite.md`（91 行）：A 段三步（入口校验〔G1 未过不得代确认〕 → 覆盖走查〔未覆盖/存疑/已覆盖三态＋G 类控标信号只标注不定性〕 → F 类时效三态走查〔fact_missing/expired/expiring_soon 四态不得混报〕＋停 G3）＋B 段成稿响应走查（三态判定/偏离表禁照抄/跨章一致只列事实/E 雷同不得定性串标）＋停 G5；每步【能力依赖：L2】＋降级指令；铁律自包含；R7 状态快照。

## [bid-technical-proposal/v0.3.0] - 2026-10-21

> 阶段 5：新增 `SKILL.lite.md`（L0 纯对话版轻量提示词，计划书 §9）。脚本与机读产物零变化。

### Added

- `SKILL.lite.md`（86 行）：五步循环单章成文（取本章要求 → 素材路由与事实取用〔无素材只出占位〕 → G4 技术路线确认〔未过不动笔〕 → 按章撰写〔每段 [[F:]]/[[S:]] 标注〕 → 背对背复核）；强制"一章一轮"（不得一次生成整本）；每步【能力依赖：L2】＋降级指令（check_facts/word_count 转人工自检三点报告）；铁律自包含；R7 状态快照。

## [repo/v1.7.29] - 2026-10-21

> 专家审核意见处置（《复核意见_v0.16质量分析_20261021》＋《审核报告_投标文件Skill建设计划v0.16_进展核验_20261021》，用户拍板 A/B1/C1/D/E 五项）：④ references 目录树闭合（技能级，另列）；计划书升 **v0.17**；s4 汇总文案修正；旧 10-19 审核报告补时效声明；本机安装 jsonschema 解锁 01 全量校验。

### Added

- `docs/投标文件Skill建设计划_v0.17.md`（由 v0.16 升版，文件同步改名）：①§5 `run_acceptance.py`/`evals/` 两处"待建"标注更新为已建；②§11 新增 **11.4 阶段 2 验收**（五步循环/②-B 偏离表逐行/check_consistency/真基探针/E 雷同转人工）与 **11.5 阶段 4 验收**（六件套/E2E 驱动器/真基试跑/记录体系/**X 层关闭前置**）两小节；③§0 按惯例登记（旧 0.0/0.0.1/0.0.2 顺延为 0.0.1/0.0.2/0.0.3）。设计正文/铁律/schema 零变更（scan_doc D1–D6 通过，表格 60 张）。
- `docs/审核报告_投标文件Skill建设计划v0.16_已完校验与未完清单.md` 头部补时效声明（快照 2026-10-19，未完清单仅对当日有效，指向进展核验报告与 CHANGELOG——复核意见 §五-1）。

### Changed

- `tests/test_stage4_regression.py`：汇总文案 "T4-1~T4-6" → "T4-1~T4-7"（实际含 T4-7；进展核验报告 §五-2）。
- `tests/test_stage3_regression.py`：T3-11 断言升 ④ v0.2.1 口径（SKILL/README 版本行＋两新 references 在位）＋T3-10b 版本登记断言 0.2.1；s3 由 59 项 → **61 项**。
- `AGENTS.md`：必跑命令计划书文件名 v0.17、s3 61 项；结构速览 ④ v0.2.1；施工前沿更新。
- 本机环境：`pip install jsonschema`（4.26.0）——`validate_plan.py`/`emit_facts.py` 走完整 schema 校验路径（此前降级为结构子集＋WARN）；技能包零三方依赖原则不变（缺失时仍优雅降级）。

### Evidence

- `python tests/validate_contract.py --write-lock` 后复跑：PASS（④ 0.2.1 入锁；C10 比对 v0.17 §7）。
- 六件套：s1 32/32、s2 64/64、**s3 61/61**、s4 44/44（文案行同步 T4-7）、`scan_doc docs/投标文件Skill建设计划_v0.17.md` D1–D6 通过。
- 镜像同步 `~/.config/opencode/skills/bid-docx-export`（robocopy 排除 `__pycache__`，SKILL.md version=0.2.1、references 5 件核对通过）。
- jsonschema 解锁验证：R2-1（① 全链含 validate_plan）在装后全绿，完整校验路径生效。

## [bid-docx-export/v0.2.1] - 2026-10-21

> references 补全版（进展核验报告 §五-1：计划书 §5 目录树要求 5 个 references，实装仅 3 个）。补齐 `样式与编号规范.md`＋`雷同与元数据清理.md`，导出行为零变化。

### Added

- `references/样式与编号规范.md`（48 行）：三档样式档优先级与回落规则、基线参数表、暗标叠加层四条规则、编号与页码口径（章名逐字/附件号 A-NN/PAGE 域/页数闭合）、正文标注处理（`[[EV:]]`/`[[F:]]`/`[[S:]]`）。
- `references/雷同与元数据清理.md`（43 行）：四道防线中 ④ 责任划分（信号判定归 ②）、元数据清理两模式字段表（修订记录红线）、verify 联动、`similarity-check.md` 格式约束（不得定性串标）、§11.3 验收对照。

### Changed

- `SKILL.md`：version 0.2.0→0.2.1；头部版本行；§三 步 1/步 6 两处加 references 指向；§七 标题与雷同自查行同步。
- `README.md`：版本行同步 v0.2.1。
- `skills-lock.json`：④ 登记版本 0.2.1（`--write-lock`）。

### Evidence

- `tests/test_stage3_regression.py`：61/61（T3-11a 升 0.2.1、T3-11c 含两新 references 在位、T3-10b 版本登记 0.2.1——`verify_docx._read_version` 动态读 SKILL.md，无需改脚本）。

## [repo/v1.7.28] - 2026-10-21

> 阶段 4（端到端串联＋真实项目试跑记录＋evals＋盲审工单）主体交付：`tests/run_acceptance.py` E2E 驱动器＋`tests/test_stage4_regression.py` 44 项永久回归＋`evals/` 目录（记录纪律／真基首条记录／D1-D2 测试卡／X 层盲审工单）。无技能包改动（阶段 4 为 repo 级，无锁/镜像动作）。阶段 4 余项＝D1/D2 用户实测回填与盲审投递合并。

### Added

- `tests/run_acceptance.py`：E2E 驱动器双模式——`verify`（只读核查：validator 链＋frontier 判定＋暗标标识扫描 05_chapters，命中即 FAIL）与 `--run`（临时副本串联，真基只读；① 重建→②-A→〔写作与偏离表由测试模拟〕→②-B→④ 七脚本）；`--json` 报告含 `rc`；暗标模式向 `verify_docx` 透传 `--identity`。
- `tests/test_stage4_regression.py`：阶段 4 永久回归 **44 项**（T4-1 全链 E2E 25〔⓪ 起步件→① G2+G1→②-A G3→③ 42 章成稿 G4→route→writing→②-B 偏离表 1266 行→G5→④ exported→终态 verify PASS〕／T4-3 跳步负例 4／T4-4 状态-产物不一致 2／T4-5 frontier 六态 6／T4-6 --json 结构 5／T4-7 暗标标识扫描 2）；合成 bid 全链自建（20 件证据命名覆盖全部任务卡）；临时目录 finally 清理。
- `evals/`：README（记录纪律四条：只记事实态/无效轮次不删/可复现/SELF-ONLY；七节记录格式；七维记分卡 V1~V7）；`records/2026-10-21_machine-chain.md`（示例市真基 verify PASS＋--run 至 G3 首条记录，⚠️ SELF-ONLY）；`trigger-tests/D1-D2-平台触发与拒绝测试卡.md`（8 句触发语料＋4 拒绝场景，用户执行后回填）；`cross-audit/盲审工单-套件设计-2026-10.md`（套件设计级盲审工单，自包含、无自审结论，投递由用户执行）。

### Changed

- `AGENTS.md`：必跑命令增至六件套（＋test_stage4）；施工前沿更新为阶段 4 主体交付；阶段 4 交付记录条目。
- `tests/run_acceptance.py`（本阶段内迭代）：JSON 报告补 `rc` 键；暗标套件级 identity 扫描实装。

### Evidence

- `python tests/validate_contract.py`：C1–C12 全绿（本次无技能包改动，锁未动）。
- 阶段回归：s1 32/32、s2 64/64、s3 59/59、**s4 44/44**（新增）。
- `python tests/scan_doc.py docs/投标文件Skill建设计划_v0.16.md`：D1–D6 通过（本次未改计划书）。
- 示例市真基：verify PASS（frontier=② G3）无副作用；--run 仅对 %TEMP% 副本（详见 evals/records/ 首条）。
- 临时件清理：`workdir/_probe_s4_ifaces.py`、`%TEMP%\s4_run_*` 已删除。

## [repo/v1.7.27] - 2026-10-21

> 阶段 3（④ bid-docx-export 排版导出）交付：④ 0.1.1→0.2.0 实装＋`tests/test_stage3_regression.py` 59 项永久回归；锁更新与镜像同步。阶段 3 收口，下一前沿＝阶段 4（端到端/evals/双模型）。

### Added

- `tests/test_stage3_regression.py`：阶段 3 永久回归 **59 项**（T3-1 入口闸门 8／T3-2~T3-4 样式档三档 12／T3-5 证据索引 6／T3-6 证据检查 4／T3-7 PDF 装配 6／T3-8 docx 生成 6／T3-9 元数据清理 3／T3-10 回读校验 6／T3-11 交付物在位 8）。全合成 bid（合成章节/任务卡/手写经典 xref 造 PDF），零三方依赖；临时目录 finally 清理。

### Changed

- `skills/bid-docx-export/`：v0.1.1→v0.2.0（见下方技能条目）。
- `skills-lock.json`：④ 登记版本 0.1.1→0.2.0（`--write-lock` 重生成）。
- `AGENTS.md`：施工前沿更新为阶段 3 交付。

### Evidence

- `python tests/validate_contract.py`：C1–C12 全绿（锁内 ④ 0.2.0）。
- `python tests/test_stage1_regression.py`：32/32；`test_stage2_regression.py`：64/64（无回退）；`test_stage3_regression.py`：59/59。
- `python tests/scan_doc.py docs/投标文件Skill建设计划_v0.16.md`：D1–D6 全部通过（本次未改计划书）。
- 镜像同步 `~/.config/opencode/skills/bid-docx-export`（备份 %TEMP%\skills_bak_t3_20261021_145551→robocopy 排除 `__pycache__`→SKILL.md version=0.2.0 核对通过）。
- 冒烟与补丁临时件（workdir/_smoke_*.py、_tmp_smoke_cc.py、probe_t3_style.py、scripts/__pycache__、%TEMP%\t3reg_*）已清理。

## [bid-docx-export/v0.2.0] - 2026-10-21

> 阶段 3 实装版：导出链七脚本（三档样式档→证据索引→五项证据检查→合订 PDF 装配→docx 生成→元数据清理→回读校验）落地；纯标准库零三方依赖（PDF/docx 均自研生成）；回读校验全过才写 `stage=exported`。雷同自查机检按计划书修订取消（转人工＋清单，G5 环节执行）。

### Added

- `scripts/_common.py`：共享模块——入口闸门（stage=recheck_confirmed／form-check 空项／②-A `expired` 联动阻断〔`expiring_soon` 不阻断〕／style_source 一致性→`failed_nodes`）、零依赖 mini YAML 读取、章节 frontmatter 解析、`[[F:]]`/`[[S:]]` 标注剔除、`persist_failed_nodes` 去重落盘。
- `scripts/pdfutil.py`：纯标准库 PDF 解析（对象表/xref/页树/count_pages）。
- `scripts/build_style_profile.py`：三档样式档——招标明示逐项采用＋空值回落基线记 `sources`；甲方模板纯标准库解析（docDefaults 字体/字号/行距/缩进＋sectPr 页边距）；通用中文基线；产出 `style-profile.yaml`＋《排版依据说明.md》（无招标要求时写明"无招标要求，采用基线"）。
- `scripts/index_evidence.py`：证据索引——PDF 实测页数（图片按 1 页计并标注）、附件号（文件名前缀优先/自动补号）、`fact_ref` 与 03 任务卡关键词匹配（匹配不上留空不猜，铁律 1）、`order`/`stats`。
- `scripts/check_evidence.py`：五项证据检查——缺件（废标级排前）/日期一致性（只比不判时效）/页数超限（500 字/页±10% 估算＋`page_limit`）/文件大小超限（`--max-mb` 或 01b 提取）/索引自洽（pages↔page_count↔order↔附件号↔文件存在性）。
- `scripts/assemble_pdf.py`：合订 PDF——纯标准库 PDF writer（A4/样式档参数/CJK 折行/避头点/页码/目录两遍法收敛）＋证据对象级合并（BFS 可达闭包＋重编号＋Pages 树重建）；`pagination.json` 自证（body/toc/chapters/evidence/total）＋合并后实测复核；超 `page_limit` rc=1（铁律 3）。
- `scripts/export_docx.py`：正文 docx——章名逐字取 01c（铁律 2）；`[[EV:]]`→「见附件A-xx（第N–M页）」（页码来自 pagination）；`[[F:]]`/`[[S:]]` 剔除；页脚 PAGE 域；creator/lastModifiedBy 出生即为空。
- `scripts/scrub_metadata.py`：元数据清理——普通标/暗标两套（creator/lastModifiedBy/Company/Template/attachedTemplate/lastPrinted/custom.xml/comments）；**修订记录不自动接受**（存在即 rc=1）；PDF `/Info` 对象级清空；暗标 `--identity` 扫页眉页脚/正文/属性，命中报事实态 rc=1（改内容归 ③）。
- `scripts/verify_docx.py`：交付前回读校验——章名逐字（01c 顺序）/占位符残留/元数据残留（含修订记录）/页数闭合（PDF 实测 vs pagination）/暗标标识；中英文空格信息态；全过才写 `stage=exported`＋`skill_versions` 登记＋交付完成块；出 `verify-report.md`。
- `references/证明材料装配规则.md`：evidence/ 目录命名、三条分工（AI 排页码/人录 issuer/valid_to/盖章位）、装配顺序、装订调整、平台降级。

### Changed

- `SKILL.md`：version 0.1.1→0.2.0；头部版本行改实装；§二 入口校验实装化（consistency-issues 缺失降信息态警告）；§三 七脚本表＋rc 语义＋逐步要点；§六 契约表补全产物；§七 能力表 v0.2.0（雷同自查取消行）；**铁律块未动**。
- `README.md`：同步 v0.2.0——输入表（`evidence/` 替代 03b 前置）、产出表、七脚本链、三档说明。

### Fixed

- 闸门/导出失败时 `failed_nodes` 去重落盘 `00_metadata.json`（metadata.schema 已声明字段，原实现只打注不落盘）。
- `scrub_metadata.py` 修订记录 rc=1 被 PDF 清理段 `rc = 0` 无条件覆盖的缺陷（T3-9b 抓出）。

### Evidence

- `python tests/test_stage3_regression.py`：59/59 PASS（含三段冒烟场景：chain/export/verify 全链）。

## [repo/v1.7.26] - 2026-10-21

> 新增套件外技能 `quantity-takeoff-building` v0.1.0 入库（房建工程量计算执行层），纳入本仓库统一管理；不参与投标技能版本化矩阵。

### Added

- `skills/quantity-takeoff-building/`：从 `~/.workbuddy/skills/` 迁入并整理，19 个运行必需文件
  - `SKILL.md`（v0.1.0）：三条铁律、六道门 G0–G5、五步闭环、输入输出契约、禁写清单、遗留待办
  - `references/`×8：量算SOP、规范版本台账、计算规则库、公式库、钢筋构造库、交叉验证清单、公差与敏感度表、输出模板
  - `scripts/`×3：`geometry.py`（面积/体积恒等式）、`rebar.py`（钢筋算量）、`check.py`（门禁/有效位数）
  - `tests/`×7：声明式 JSON 用例 6 份 + `run_tests.py`，共 35 断言
  - `README.md`：与 `delivery-audit` 同格式，含**覆盖范围如实表**与超额声明提示
- `docs/quantity-takeoff-CHANGELOG.md`：技能级变更记录（由技能包内移出，遵守"技能包只放运行必需文件"）
- `docs/quantity-takeoff-总体编制计划书.md`、`docs/quantity-takeoff-机电计量设计计划书.md`、`docs/quantity-takeoff-核查报告-20261021.md`：设计文档归档

### Changed

- `skills-lock.json` `_scope.out_of_scope` 增 `quantity-takeoff-building` 声明（沿用 `delivery-audit` / `business-contract-review` 先例，不进版本化矩阵）
- `AGENTS.md` 结构速览补记该技能及其实测状态

### Evidence

- `python tests/validate_contract.py`：C1–C12 全绿（新技能不在锁内，未影响既有契约）
- `python scripts/geometry.py && python scripts/rebar.py && python scripts/check.py`：三者自测通过
- `python tests/run_tests.py`：**35/35 PASS**
- 仓库 ↔ 运行态 `diff -rq`：字节级一致（20 文件）

### Known limitations（如实登记）

- **覆盖范围仅混凝土、钢筋、依附几何的模板**；砌体/钢结构/桩基/门窗/屋面/防水/保温/楼地面为"待核实"骨架，**不可用**
- **机电安装（给排水/电气/暖通/消防）覆盖为零**，仅有设计文档，未实现
- `SKILL.md` frontmatter 的"通用房建"表述为**超额声明**，尚未修正（待用户裁定）
- 柱高冲突（C-01/C-02）未闭环：量测 1487.4 mm vs 历史值反推 2500 mm，偏差 40.4%，需人工读图确认
- 规范条文可追溯性未达标：M1/M2/M3 边界均无条文原文，Part B 规则库多为"待核实"


## [repo/v1.7.25] - 2026-10-21

> 阶段 2 第二步：②-B 成稿响应检查实装（② `bid-compliance-check` 0.3.3→0.4.0），补计划书 §11.2 验收 #5 欠账（偏离表逐条无合并/跳条）与 #7 欠账（跨章一致性埋点实测）。

### Changed

- `tests/test_stage2_regression.py` 扩为 64 项（+28）：T2-9 ②-B 偏离表逐行（正例 rc=0＋stage 写回 rechecking；负例跳条/照抄〔F3〕/废标级负偏离/判定空白/出处断链/自造行全检出＋A-lite 残留【待填】给位置/缺章未响应；stage 不符 rc=2 且不写回）；T2-10 跨章一致性（工期/金额同语义多值 ⚠️、名称变体、同值异形〔80万＝捌拾万元整〕不误报、位置粒度、日期中「12月」不当工期、rc=2 入口）。
- `tests/test_stage1_regression.py` R3-1 断言更新至 v0.4.0 口径：名称变体/编号异值由信息态升 ⚠️ 级（rc 0→1），加 stdout 汇总断言；purchaser/年份不误报子句保留。
- `skills-lock.json`（`--write-lock`）：② 0.3.3→0.4.0。
- 运行目录 `~/.config/opencode/skills/bid-compliance-check` 镜像同步（镜像前备份于 `%TEMP%\skills_bak_20261021_2b`；robocopy 排除 `__pycache__`；SKILL.md version=0.4.0 已验）。
- `AGENTS.md` 同步阶段 2 第二步完成状态。

### Evidence

- `python tests/test_stage2_regression.py`：64/64 PASS（其中 T2-9 抓出并修复 mode B 两处真 bug：SKILL.md 路径差一级〔scripts/ 下找不到〕、退出码不透传〔`main()` 未 `sys.exit`〕）。
- `python tests/test_stage1_regression.py`：32/32 PASS（R3-1 已按 v0.4.0 行为更新）。
- `python tests/validate_contract.py`：C1–C12 全绿（锁内 ② 0.4.0）。
- `python tests/scan_doc.py docs/投标文件Skill建设计划_v0.16.md`：D1–D6 PASS（本次未改计划书）。
- 示例市真基探针（`workdir/acceptance/probe_02B/`，一次性，不入 tests/）：1266 条偏离表埋 4 缺陷（跳条 sp-010／重行 sp-020／照抄 sp-003／负偏离废标级 sp-005）**全检出**，错误 4＋废标级 1、rc=1、stage→rechecking、compliance-report.md 追加「## 十一、②-B 成稿响应复查」节；A-lite 79 卡 vs 3 合成章＝已响应 1／响应不足 0／未响应 58／证据类 20（scan 卡归证据类口径正确）；3 章 3 埋点（工期 180 vs 150 日历天／总价 5000万 vs 4800万／名称变体）**全检出** rc=1，同值异形（保证金 80万＝捌拾万元整）只记 ℹ️ 不误报。

## [bid-compliance-check/v0.4.0] - 2026-10-21

> 成稿响应检查实装（阶段 2 第二步）：②-B 从规划落为机检——A-lite 任务卡成稿三态、B 偏离表逐行、F 复述 ②-A 结论、C 类跨章一致性升 v0.4.0。E 雷同与暗标终检仍属 G5 人工项。

### Added

- `scripts/check_compliance.py --mode B`：入口校验（stage=writing，rechecking 为重跑态；缺前置阻断零产物 rc=2）→ 执行中写回 `stage=rechecking` 并登记 `skill_versions` → A-lite 三态（已响应／响应不足〔残留【待填/待确认】给章节·段落·行号位置〕／未响应〔章节文件缺失〕／证据类〔scan 卡〕）→ B 偏离表逐行（跳条/多行〔01b 无此条目〕/重行/照抄〔含限定符要求值照抄＝未响应，F3〕/响应值或判定空白/非法判定值/负偏离废标级单列〔`no_negative_allowed` 条目，🔴〕/出处断链）→ F 类复述 `qual_timing` 结论不重判 → G5 指引（不自动写 recheck_confirmed）；退出码 0/1/2。
- 输出：`06_compliance/deviation-table.md`（②-B 逐条判定，覆盖写：行数对账＋差异清单＋废标级单列＋警告四节）＋ `compliance-report.md` 追加「## 十一、②-B 成稿响应复查」节（保留 ②-A 记录追加不覆盖）；B 类前置人工件缺失时 `blocked_by_contract` 阻断但 A-lite/F 照常出。

### Changed

- `scripts/check_consistency.py` 升 v0.4.0（跨章一致性全套件唯一实现）：位置粒度「章节（number title，id）· 第 N 段 · L 行：原文片段」（frontmatter 剥离＋body_offset 换算文件绝对行号＋空行分块段落号）；工期/金额**同语义多值检测**（工期按单位族〔day/month〕＋语境词、金额按行内关键词归类〔总价/保证金〕，组内 ≥2 值即 ⚠️）；**同值异形不误报**（中文大写/货币符号/千分位/数字+单位四形态归一到元值，数值等值只记 ℹ️——投标函大小写并书不再误报）；工期扫描前先剔除行内日期（防「2026年12月15日」的「12月」误判为月工期）；名称变体先置换招标人全名行（防业主名共前缀误报）；rc=1 即 G5 须逐条闭环。
- `references/响应偏离表模板.md`：首列改**条目id**（照录 01b 主键 sp-xxx，机检对行依据）；新增「人工填写落点」契约——人工填 `08_business/deviation-table.md`（计划书 §5.1：08_business 为人工填写区，Skill 只读），②-B 机检输入；§四 列 mode B 机检项（跳条/多行/重行/照抄/空白/废标级/断链）。
- `SKILL.md`：version 0.3.3→0.4.0；头部版本史补 v0.4.0；§六 产出表 ②-B 由「规划未实产」改实产三件（deviation-table.md ②-B 模式／consistency-issues.md／compliance-report.md 追加节；similarity-check.md 仍规划）；§七 能力表升 v0.4.0（②-B 四行实装＋E 雷同仍 ⏳）；运行说明增 ②-B 用法块（入口/前置人工件/退出码/C 类另跑）。铁律块未动。
- `README.md`：同步 v0.4.0（②-B 运行节＋版本记录＋脚本表）。

### Fixed

- `check_compliance.py` mode B：`SKILL.md` 路径解析差一级（原按 scripts/ 同级找，`FileNotFoundError`；改 `dirname(dirname(__file__))` 技能根）。
- `check_compliance.py`：`main()` 返回值未透传（`if __name__` 裸调 `main()`，退出码恒 0；改 `sys.exit(main())`＋补 import sys）——G5 判定依赖 0/1/2，不透传即契约失效。

## [repo/v1.7.24] - 2026-10-21

> 阶段 2 开工（计划书 §11 行序：③ 在前）。③ `bid-technical-proposal` 由零脚本骨架升为正文能力版 v0.2.0；本步不含 ②-B 偏离表与 G5 成稿终检（阶段 2 余项，另步施工）。

### Changed

- `tests/test_stage2_regression.py` 新增（36 项永久回归入口）：T2-1 chapter.schema 契约正负例、T2-2/T2-3 check_facts 正负例（E1–E3）、T2-4 过渡句降级、T2-5 R1/R2 联动（E4/W1）、T2-6 字数口径单元、T2-7 word_count 集成（MISSING/偏差/孤儿/outline 缺失）、T2-8 ③ v0.2.0 交付物在位与铁律/C9 锚防呆。
- `tests/fixtures/05_chapters.sample.md` 新增（合法章节样例，供 T2-1 与 ②-B 后续复用）。
- `skills-lock.json`（`--write-lock`）：③ 0.1.1→0.2.0。
- 运行目录 `~/.config/opencode/skills/bid-technical-proposal` 镜像同步（镜像前备份于 `%TEMP%\skills_bak_20261021_090639`；robocopy 排除 `__pycache__`；15 文件与源逐文件一致，SKILL.md version=0.2.0 已验）。
- `AGENTS.md` 同步阶段 2 开工状态、③ 版本与新增回归入口。

### Evidence

- `python tests/test_stage2_regression.py`：36/36 PASS。
- `python tests/test_stage1_regression.py`：32/32 PASS（无回退）。
- `python tests/validate_contract.py`：C1–C12 全绿（锁内 ③ 0.2.0）。
- `python tests/scan_doc.py docs/投标文件Skill建设计划_v0.16.md`：D1–D6 PASS（本次未改计划书）。

## [bid-technical-proposal/v0.2.0] - 2026-10-21

> 正文能力版：五步写作循环（任务卡→素材路由→G4 技术路线确认→撰写→背对背复核）实装，配双自检脚本与 5 份写作规范。出口=全部章节 `final` 且 04_outline 节点全 `done`。

### Added

- `assets/chapter.schema.json`：05_chapters frontmatter 契约（schema_version/chapter_id/number/title/status/word_target/g4 四必填＋route_summary 3–5 条）。③ 单副本，不入 skills-lock（计划书 §5.2 矩阵）。
- `scripts/check_facts.py`：事实引用核验——E1 未知 [[F:]]／E2 未知 [[S:]]／E3 无来源段落（纯标题、占位段、[[EV:]] 豁免；单行无数字过渡句降级 W1）／E4 引用缺 source（R1）／W1 事实超 12 个月（R2）／W2 可识别未解析。事实库加载 02_facts.yaml 优先、退 02_facts.md 存在性。
- `scripts/word_count.py`：篇幅统计（对照 04_outline.word_target）——CJK 逐字＋拉丁词口径；MISSING／⚠超偏差（|偏差|>40%）／孤儿文件三类标记；outline 缺失 rc=2。
- `references/章节写作五步循环.md`（主流程）／`写作规范.md`（段落/反 AI 味/表格边界）／`工程类技术标结构参考.md`（内容组织参考，让位于 01c）／`暗标写作规范.md`（identity_ban 禁项对照）／`图表与题注规范.md`（图表编号与来源标注）。

### Changed

- `SKILL.md`：version 0.1.1→0.2.0；入口校验增第 5 步（bid_mode 判定分流）；§三 五步循环表实装化；出口条件改为「全部章节 final＋outline 节点全 done」；跨章一致性注明 check_consistency.py 仍为骨架（②-B 范畴）；§六 契约表登记 03 任务卡 v0.2 与 chapter.schema.json；§七 能力表 v0.2.0 全✅（②-B 项除外）。铁律块未动。
- `README.md`：同步 v0.2.0 与脚本表。

## [repo/v1.7.23] - 2026-10-19

> C 系列收口：阶段 1 §11.2 十一条逐条复跑＋两轨对账缺口修复（`01_tender-facts.json` 53→67 条），① 补 3 张资格卡（v0.21.0）。阶段 1 是否关闭以验收记录复验节结论为准。

### Changed

- 示例市 `01_tender-facts.json`（`workdir/acceptance/bid_base/`）按七类清单 Markdown 序列化重建：
  - 补 14 条缺失/拆分项：① 确认收到澄清、开标、保证金到账、保证金退还、异议渠道；② 信誉（由「财务/信誉」拆出，c-0011 收窄为财务）、其他人员、近年诉讼；⑤ 付款方式；⑥ 履约担保、发包人支付担保；⑦ 解密时限/逾期、递交、保证金载体（新增 c-0054–c-0067）。
  - ④ 散文表化为 6 行（内容不增不减，c-0026–c-0031 对齐序号 1–6）。
  - `local_no` 统一改为七类清单「序号」列（不再混用条款号）；67 条类内重号 0、id 唯一。
- `skills/bid-response-plan/scripts/build_task_cards.py`：`TASKS` 补 3 张资格卡（c-0059 信誉／c-0060 其他人员／c-0061 近年诉讼），任务卡 76→79、资格卡 7→10、`coverage.unmapped` 仍为空。
- 重生成 `03_bid-plan.json`、`04_outline.json`（旧版结构→现行 `build_04` 结构，42 节点）、`素材缺口清单.md`；`01c` 沿用 B4 已验版本。
- `docs/v0.16_阶段1收口施工清单.md` 两项 B 系列未闭观察：04 旧版结构已闭；03c n-1131 短名保留（常量自持，不影响 01c）。
- `docs/投标文件Skill建设计划_v0.16.md` §0 补 ⓪ v1.5.1 版本引用登记行（修 `scan_doc` D4 红灯，属版本引用刷新、不改规则）。
- `docs/v0.16_阶段1验收记录.md` 追加「八、阶段 1 复验结论」（历史不通过节原样保留），并修正历史段 3 处跨文档引用格式以过 `scan_doc --note`。
- `docs/v0.16_阶段0验收记录.md`／`v0.16_触发实测记录.md`／`v0.16_delta_提取规则增量.md` 补 ⓪ v1.5.1 版本引用刷新行；delta 跨文档引用补「计划书／⓪ SKILL.md」前缀（只改引用格式与版本注记，不改历史判定）。
- 运行目录 `~/.config/opencode/skills/` 五技能镜像同步（镜像前备份于临时目录；⓪ 1.5.1／① 0.21.0／② 0.3.3／③④ 0.1.1）。
- `AGENTS.md` 同步阶段 1 关闭状态、① 版本与运行目录同步说明。

### Evidence

- C2 两轨对账：Markdown 67 行＝JSON 67 条，逐类一致（①②③④⑤⑥⑦ = 12/10/11/6/6/9/13）。
- `emit_facts.py --expected-clauses 67 --expected-total 100` rc=0、无警告；`validate_plan.py` rc=0（jsonschema 未装仅 WARN）；`check_compliance.py --mode A` rc=0（资格项 10、未响应 0、孤儿卡 0、商务表 24/24）；`check_business.py` rc=0。
- 负例复跑：删映射告警 PASS；注入 10 条否决级条款 `cross_fatal_no_card` 10→20（≥8）PASS；注入金额 rc=1 PASS；资质三态不混报 PASS。
- 抽 10 张任务卡：来源可解析／章节在 01c／response_form 齐备，10/10 一致。

## [bid-response-plan/v0.21.0] - 2026-10-19

> 任务卡映射补 3 张资格卡，承接 C2 序列化重建后新增的 ② 条目。

### Added

- `TASKS`：c-0059 信誉（4 项信用查询截图）／c-0060 其他主要人员（设计/施工/安全负责人、机械设备、管理机构）／c-0061 近年诉讼（2022-01-01 至今重大诉讼及仲裁），均为 `blocked_by_facts`。

### Changed

- `SKILL.md` frontmatter 0.20.0→0.21.0＋版本史行；`skills-lock.json` 同步。

## [repo/v1.7.22] - 2026-10-19

> B 系列收官：示例市 ⓪ 历史产物 63 处漂移清零＋#0/#2 项目级复验通过。**仅改 `workdir/acceptance/` 副本与文档，无技能代码/契约变更**（技能版本与 `skills-lock.json` 不动）。

### Changed

- 示例市 `01_tender-facts.json`（`workdir/acceptance/bid_base/`）：
  - B1：52 处空 `review_stage` 按「七类→六环节」基础映射＋3 处内容例外（c-0006→other、c-0007→scoring、c-0032→form）填齐，经用户确认；分布 form 16／responsive 11／waste 11／qualification 7／scoring 7／other 1。
  - B2：`clarifications[]` 6 项、`system_clues[]` 3 项由字符串改为 `{"text": 原文}`；`meta.submission_form` `mixed`→`电子`（混合递交取主形态，c-0044 `remark` 记明依据）；`clauses[].price_cap_form` `draft_blank`→`pending`（`value_state` 仍为 `draft_blank`）。
  - B3：`scoring` 补 `weight`（0.1/0.4/0.5）、`total_stated=100`、`weight_basis`（原文摘录）→ `emit_facts.py --expected-total 100` rc=0、Σ(分值×权重)=100、无警告。
  - 附带修正：`local_no` 类内重号 2 对（均 3.7.5）按原文出处补记 `3.7.5(T1R37)`，编号唯一性硬错误清零。
  - B4：重生成 `01c_format-outline.json`（n-1131 标题补回适用性括号），`verify_format_chapters.py` 42/42 PASS；`03_bid-plan.json` 重算无变化。
- `docs/v0.16_阶段1收口施工清单.md`：B 系列标记「B1–B4 全部已闭」，登记判定口径与两项未闭观察（03c n-1131 短名、04 旧版结构未重生成）。

### Evidence

- `emit_facts.py` rc=0（结构校验＋自检＋D5 闭合）；B1 提案件与逐条表存 `workdir/acceptance/bid_base/B1_review_stage_提案.md`。
- `verify_format_chapters.py` PASS 42 节点（fixture `tests/fixtures/07_format_headings.sample-project.json`）。
- `scan_doc.py docs/v0.16_阶段1收口施工清单.md --note` PASS。

## [repo/v1.7.21] - 2026-10-19

> A 系列收官：`01b` 第五章 9.工程管理（P5139–P5389）78 行入库（sp-1189–1266）——**第五章 1–9 节全量覆盖**（1264 行）；阶段 1 的 A1–A4 全部完成。① 随 bump 0.20.0。

### Changed

- `skills/bid-response-plan/scripts/parse_spec_items.py`：SPEC_ITEMS 追加 78 行（A4：9.1 工程质量管理 22＋9.2 HSE 6＋9.3 工程协调和管理 12＋9.4 工程总体管理 10＋9.5 合同履行 16＋9.6 分包 12）。拆分登记——5 组标准清单按组行（配电系统 11 项 P5155–P5165／并网接口 5 项 P5167–P5171／电气仪表 9 项 P5173–P5181／质量检验评定 15 项 P5183–P5197／安全技术 3 项 P5199–P5201）；3 组管理制度清单按组行（工程管理 37 项 P5205–P5241／工程质量 15 项 P5243–P5257／安全文明施工 34 项 P5259–P5292）；月报内容 8 项按组行（P5359–P5366）；主题标号段与「需具备：」「包括但不限于：」等引出句不抽；T40（管辖段 P5383）/T41（P5385–P5387）/T42（P5389）为承包人填写空白表，不拆行只登记。docstring 覆盖状态改为"第五章 1–9 节全量完成"（删除挂起小节）；`SOURCE.page_range`、`main()` 提示语同步。
- `tests/check_01b_rawtext.py` 硬编码计数行同步（已全量 9 节、挂起 0 节）。
- `skills-lock.json`（`--write-lock`）：① 0.20.0。

### Evidence

- `check_01b_rawtext` PASS（1266 行引文与 `full_dump.txt` 逐行一致，含 9 组锚点跨段引文）；阶段 1 回归 32/32；契约校验 C1–C12 PASS（锁内 ① 0.20.0）。
- 产物再生 `workdir/acceptance/bid_base/01b_spec-items.json`：1266 条（第五章 1264＋跨章节 2）。

## [bid-response-plan/v0.20.0] - 2026-10-19

> ① `01b` 第五章收官（A4）：新增 9.工程管理 78 行（sp-1189–1266），第五章 1–9 节全量覆盖。

### Added

- 9.1 工程质量管理 22 行：最低限度要求与优质产品服务／系统拟定与设备布置负责／强制性标准／异议与差异表／平面布置优化不调价／成套设备全责／一期编码延续／中国法律与 ISO/IEC／标准采用四项原则／提交全部标准／5 组标准清单组行／标准矛盾取高／3 组管理制度清单组行（37＋15＋34）。
- 9.2 HSE 6 行：完整 HSE 体系／方案提出与方针／a 程序文件清单／b 危险因素与环境因素清单／c 管理措施／d 管理网络。
- 9.3 工程协调和管理 12 行：现场项目经理职权与委派／代表函件效力／监理制与接受监理／总监理工程师／客观公正处理／承包人职责（合同管理 2＋合同履行 4）。
- 9.4 工程总体管理 10 行：进度控制 2／设计审查 5（审查率 100%、未批准不得施工、变更报批、信函抄送、不构成免责）／工程程序与设计控制文件 3。
- 9.5 合同履行 16 行：通讯 3／文件传递 1／会议 3／设计联络会 2／周月会 1／专题会 2／周报月报 3／月报内容 8 项组行 1。
- 9.6 分包 12 行：分包商资格 4（资质业绩、新设备成熟业绩、监督指导与整改补救、直接付款扣回）／分包商选择 6（招标、技术规范书审查、内容与调研、评标参与、采购合同条款、合同份数与长名单）／备选名单备注 2（施工/设计分包资质评审）。

### Changed

- `SKILL.md` frontmatter 0.19.0→0.20.0＋版本史行；docstring 覆盖状态标记改为 ✅ 全量完成；`SOURCE.page_range`、`main()` 提示语、`tests/check_01b_rawtext.py` 计数行同步。

### Evidence

- 机检三门全绿：`check_01b_rawtext` PASS、阶段 1 回归 32/32、契约校验 C1–C12 PASS；78 行引文全部首尾落原文边界。

## [repo/v1.7.20] - 2026-10-19

> 施工清单 A3 收官：`01b` 第五章 7.4 设备监造及验收（P4843–P4891）43 行入库（sp-1146–1188）——7.施工质量要求 279 行全节完成，第五章已全量 8 节（仅余 9.工程管理）。① 随 bump 0.19.0。

### Changed

- `skills/bid-response-plan/scripts/parse_spec_items.py`：SPEC_ITEMS 追加 43 行（A3d：7.4.1 监造与检验 27＋7.4.2 催交催运与现场检验 13＋7.4.3 清退出场 1＋7.4.4 性能验收范围 1＋7.4.5 性能验收标准 1）。拆分登记——7.4.1 标题「（不适用，但承包人应提供配合工作）」按段抽取 1 行（保留"不适用"口径）；监造职责（1）–（20）逐条；7.4.2/7.4.3/7.4.4/7.4.5 无编号义务段逐段抽。docstring 覆盖状态由"已全量 7 节＋部分全量 1 节"改为"已全量 8 节"、删除部分全量小节；`SOURCE.page_range`、`main()` 提示语同步。
- `tests/check_01b_rawtext.py` 硬编码计数行同步（已全量 8 节，7.施工质量 279，sp-910–1188）。
- `skills-lock.json`（`--write-lock`）：① 0.19.0。

### Evidence

- `check_01b_rawtext` PASS（1188 行引文与 `full_dump.txt` 逐行一致，含 P4844 标题段）；阶段 1 回归 32/32；契约校验 C1–C12 PASS（锁内 ① 0.19.0）。
- 产物再生 `workdir/acceptance/bid_base/01b_spec-items.json`：1188 条。

## [bid-response-plan/v0.19.0] - 2026-10-19

> ① `01b` 第五章 7.施工质量要求收官（A3d）：新增 7.4 设备监造及验收 43 行（sp-1146–1188），7 全节完成（279 行）。

### Added

- 7.4.1 监造与检验 27 行：不适用但应配合工作（标题段）／委托有资质监造分包方按《电力设备监造技术导则》监造／总监造工程师与人员资质履历报审／监造规划与细则及质量控制计划报审／监造职责（1）–（20）逐条／监造成果整理报告与竣工移交／关键活动通知发包人及异议重检／在制物件覆盖前通知。
- 7.4.2 催交、催运与现场检验 13 行：催交催运／监理检验与异议核查／检验前 5 天通知与第三方重检费用／偏差预警／附加与重新检验及费用归属／拒收／强制性检验／工厂-现场-验收三阶段／试验计划报审／72 小时通知／试验报告与准确性责任／附加检验费用／合同外试验资料协助。
- 7.4.3 清退出场 1 行：不合格且无法修复的设备材料清退更换。
- 7.4.4 性能验收试验范围 1 行：风机、塔筒、主变、箱变、GIS、SVG、储能；合格签发性能考核验收证书。
- 7.4.5 性能验收试验标准 1 行：按设备合同技术协议，发包人有权调整抽检方式。

### Changed

- `SKILL.md` frontmatter 0.18.0→0.19.0＋版本史行；docstring 覆盖状态改为"已全量 8 节"（删除"部分全量"小节）；`SOURCE.page_range`、`main()` 提示语、`tests/check_01b_rawtext.py` 计数行同步。

### Evidence

- 机检三门全绿：`check_01b_rawtext` PASS、阶段 1 回归 32/32、契约校验 C1–C12 PASS；43 行引文全部首尾落原文边界。

## [repo/v1.7.19] - 2026-10-19

> 施工清单 A3 续批：`01b` 第五章 7.3.7–7.3.12（P4765–P4842）52 行入库（sp-1094–1145）——7.3 全节完成（98 行），7.施工质量累计 236 行；余 7.4 设备监造及验收挂起。① 随 bump 0.18.0。

### Changed

- `skills/bid-response-plan/scripts/parse_spec_items.py`：SPEC_ITEMS 追加 52 行（A3c2：7.3.7 安装 4＋7.3.8 调试运行 7＋7.3.9 验收与交付 20＋7.3.10 会议 3＋7.3.11 文档记录质量信息 17＋7.3.12 安全标准化 1）；docstring 覆盖状态/`SOURCE.page_range`、`main()` 提示语同步。拆分登记——7.3.7/7.3.8/7.3.9/7.3.10/7.3.11 的 1）–4）主题标号段、「（1）概述」「（2）到货验收」「（3）设备安装前验收」「3）工程验收」等结构标号段不抽，其下义务段逐段抽；开箱检查 a/b/c 逐条；移交清单（1）–（7）逐条。
- `tests/check_01b_rawtext.py` 硬编码计数行同步（部分 7.施工质量 236，sp-910–1145）。
- `skills-lock.json`（`--write-lock`）：① 0.18.0。

### Evidence

- `check_01b_rawtext` PASS（1145 行引文与 `full_dump.txt` 逐行一致）；阶段 1 回归 32/32；契约校验 C1–C12 PASS（锁内 ① 0.18.0）。
- 产物再生 `workdir/acceptance/bid_base/01b_spec-items.json`：1145 条。

## [bid-response-plan/v0.18.0] - 2026-10-19

> ① `01b` 第五章 7.施工质量要求续批（A3c2）：新增 7.3.7–7.3.12 52 行（sp-1094–1145），7.3 全节完成。

### Added

- 7.3.7 安装部分质量保证要求 4 行：安装前准备检查／安装过程要求／安装后检查与验收／文件记录汇总报备。
- 7.3.8 调试运行部分 7 行：调试前准备检查／调试领导小组／服从试运指挥部／自采与发包人采购设备厂家配合／调试过程要求／调试后试验／文件记录汇总报备。
- 7.3.9 验收与交付 20 行：材料取样送检与一致性／质量证明文件／设备全新要求／材料验收规范记录／设备验收两步／到货验收责任／随机文件记录／开箱检查组织／a–c 检查内容逐条／不符合项处理／土建与安装调试中间交接／工序验收签证／三级验收评定／并网竣工验收组织与费用／入网许可证／验收申请与静态检查／验收前质量检查／竣工资料整理移交。
- 7.3.10 会议要求 3 行：周例会与周报／月例会与月报／专题会与纪要审批。
- 7.3.11 文档、记录和质量信息管理 17 行：档案整理与交接通知／文件控制机构／网络化归档／记录查阅／阶段文件清单备案／（1）–（7）移交清单逐条／记录表格统一格式／记录规格编目／质量信息管理目标／信息提供／问题与趋势报告。
- 7.3.12 安全标准化管理要求 1 行：按《安全管理协议》实施安全标准化管理。

### Changed

- `SKILL.md` frontmatter 0.17.0→0.18.0＋版本史行；docstring 覆盖状态/拆分登记；`SOURCE.page_range`、`main()` 提示语、`tests/check_01b_rawtext.py` 计数行同步。

### Evidence

- 机检三门全绿：`check_01b_rawtext` PASS、阶段 1 回归 32/32、契约校验 C1–C12 PASS；52 行引文全部首尾落原文边界。

## [repo/v1.7.18] - 2026-10-19

> 施工清单 A3 续批：`01b` 第五章 7.3.1–7.3.6（P4702–P4764）46 行入库（sp-1048–1093）——7.施工质量累计 184 行；余 7.3.7–7.3.12、7.4 挂起。① 随 bump 0.17.0。

### Changed

- `skills/bid-response-plan/scripts/parse_spec_items.py`：SPEC_ITEMS 追加 46 行（A3c1：7.3.1 概述 2＋7.3.2 管理体系 11＋7.3.3 施工质量控制与检验 12＋7.3.4 计量测量 2＋7.3.5 项目质量计划 15＋7.3.6 不符合项与质量事故 4）；docstring 覆盖状态/`SOURCE.page_range`、`main()` 提示语同步。拆分登记——7.3.2「1）承包人及分包人的管理体系要求」「2）工程监理与质量监督」及其（1）（2）主题标号段、7.3.5「1）–4）」主题标号段不抽，其下义务段逐段抽；7.3.3（1）–（11）逐条，P4727 无编号培训义务独立 1 行。
- `tests/check_01b_rawtext.py` 硬编码计数行同步（部分 7.施工质量 184，sp-910–1093）。
- `skills-lock.json`（`--write-lock`）：① 0.17.0。

### Evidence

- `check_01b_rawtext` PASS（1093 行引文与 `full_dump.txt` 逐行一致）；阶段 1 回归 32/32；契约校验 C1–C12 PASS（锁内 ① 0.17.0）。
- 产物再生 `workdir/acceptance/bid_base/01b_spec-items.json`：1093 条。

## [bid-response-plan/v0.17.0] - 2026-10-19

> ① `01b` 第五章 7.施工质量要求续批（A3c1）：新增 7.3.1–7.3.6 土建、安装、调试的质量保证要求 46 行（sp-1048–1093）。

### Added

- 7.3.1 概述 2 行：工程施工质量目标（优良/创能建杯）／建立并运行质量体系或质量保证大纲。
- 7.3.2 管理体系要求 11 行：项目质量管理组织与分包人质量控制部门／分包商 ISO9001 体系或质保大纲／证书手册程序文件提交／按批准程序质保质控与建档备案／监理单位选择与配合／承包人管理监理单位／质量监督四层次与外部监督／分包商监督检查制度与计划报批／监督立项与证书费用／组织自我监督／质量监督记录统一管理与移交。
- 7.3.3 施工质量控制和质量检验 12 行：（1）开工申请–（11）贯标逐条，含人员资格与特殊工种持证、重要工艺培训、禁止再分包、四新技术认可、材料机具报审。
- 7.3.4 计量和测量管理 2 行：计量器具检定与报审／统一设备档案台账备案。
- 7.3.5 项目质量计划 15 行：承包人总体质量计划（编制审批/质控点/范本）＋分包商质量计划（审查批准/质控点/有效性/范本）＋W/H 点 24 小时通知与补签＋隐蔽工程 H 点与揭露检查＋上道工序验收＋ERP 配合＋见证责任记录＋一票否决权。
- 7.3.6 不符合项、质量事故事件管理 4 行：不符合项程序处理与封闭记录／统一档案台账／质量问题按分类程序／质量事故 2 小时报告与调查。

### Changed

- `SKILL.md` frontmatter 0.16.0→0.17.0＋版本史行；docstring 覆盖状态/拆分登记；`SOURCE.page_range`、`main()` 提示语、`tests/check_01b_rawtext.py` 计数行同步。

### Evidence

- 机检三门全绿：`check_01b_rawtext` PASS、阶段 1 回归 32/32、契约校验 C1–C12 PASS；46 行引文全部首尾落原文边界。

## [repo/v1.7.17] - 2026-10-19

> 施工清单 A3 续批：`01b` 第五章 7.施工质量要求 7.2 设备采购的质量保证要求（P4571–P4701）95 行入库（sp-953–1047）——7.施工质量累计 138 行，余 7.3 土建安装调试/7.4 设备监造及验收挂起。① 随 bump 0.16.0（见 `bid-response-plan/v0.16.0`）。

### Changed

- `skills/bid-response-plan/scripts/parse_spec_items.py`：SPEC_ITEMS 追加 95 行（A3b=7.2：7.2.1 概述 4＋7.2.2 管理体系 3＋7.2.3 责任与权利 18＋7.2.4 质量计划与监督 15＋7.2.5 设备监造 5＋7.2.6 第三方监督 6＋7.2.7 完工报告与符合申明 10＋7.2.8 分包质量控制 5＋7.2.9 不符合项分类处理 16＋7.2.10 报告及会议 11＋7.2.11 文档 2）；docstring 覆盖状态/`SOURCE.page_range`、`main()` 提示语同步。拆分登记——7.2.1 概述引言 P4573、购买方定义 P4578、第三方定义 P4633 不抽；纯主题标号段（1）责任/2）权利/1）审查批准质量计划/…/4）专题会及「H点和W点定义」「E类不符合项」等不抽，其下义务段逐段抽；A/B/C 级设备范围按组 3 行；I类/E类/E1/E2 不符合项逐条。
- `tests/check_01b_rawtext.py` 硬编码计数行同步（部分 7.施工质量 138，sp-910–1047）。
- `skills-lock.json`（`--write-lock`）：① 0.16.0。

### Evidence

- `check_01b_rawtext` PASS（1047 行引文与 `full_dump.txt` 逐行一致）；阶段 1 回归 32/32；契约校验 C1–C12 PASS（锁内 ① 0.16.0）。
- 产物再生 `workdir/acceptance/bid_base/01b_spec-items.json`：1047 条，stdlib 结构自检逐键符合（本机无 jsonschema，降级口径已登记）。

## [bid-response-plan/v0.16.0] - 2026-10-19

> ① `01b` 第五章 7.施工质量要求续批（A3b）：新增 7.2 设备采购的质量保证要求 95 行（sp-953–1047）。

### Added

- 7.2 设备采购的质量保证要求 95 行（sp-953–1047）：
  - 7.2.1 概述 4 行：A/B/C 级质量保证级别分类＋A/B/C 级设备范围（按组 3 行）。
  - 7.2.2 设备供应方管理体系要求 3 行：ISO9001 体系／证书与手册/程序清单／按批准程序质保质控与资料建档备案。
  - 7.2.3 承包人及设备供应方的责任和发包人的权利 18 行：责任（1）–（6）及续段（文件清单/费用/纠正措施/质量责任/协助/驻厂条件/合同传递）＋发包人权利（1）–（7）（进入区域/参会/重新试验/中止制造及条件清单/备忘录与观察意见单/不符合项报告/权利传递）。
  - 7.2.4 质量计划和质量监督 15 行：审查批准质量计划（5 天提交/两周反馈/升版批准/监督点变更/质量计划内容组行）＋质保等级 A/B/C 监督要求（3 行）＋W/H 点通知程序（提前 5 工作日/定义/试验程序 10-5 天/顺延/通知单信息/未通知后果）。
  - 7.2.5 承包人设备监造活动 5 行：监造程序计划人员与环节／见证点通知／发包人监督签字／出席 H/W 点／程序计划资质报批。
  - 7.2.6 第三方监督 6 行：范围／聘请与传递／境外双重法定监督／费用／质量文件抄送／报告纳入完工报告。
  - 7.2.7 制造完工报告和制造符合申明 10 行：报告内容（2 行）／逐步完成／发运前通知／审查放行／补充放行／最终组卷／符合申明（提供/内容/签名日期）。
  - 7.2.8 对设备供应方分包的质量控制 5 行：分包条件与评审／承担分包责任／配套件进口件清单／供应方名单报批与厂家评审／分包汇总报告。
  - 7.2.9 不符合项分类及处理要求 16 行：I类/E类定义／E类情形／E1/E2 定义／E2 变更情形／书面记录／报告说明／论证文件／查阅权／月度清单／入完工报告／全部责任／E类报审／执行报告关闭／深入调查。
  - 7.2.10 报告及会议要求 11 行：开工会（原则/目的/时间/进度计划）＋质量周报（作用/严重问题）＋月进度会（目的/组织/时间）＋专题会（情形/程序）。
  - 7.2.11 文档要求 2 行：记录保留查阅／制造阶段文件清单登记造册备案。

### Changed

- `SKILL.md` frontmatter 0.15.0→0.16.0＋版本史行；docstring 覆盖状态/拆分登记；`SOURCE.page_range`、`main()` 提示语、`tests/check_01b_rawtext.py` 计数行同步。

### Evidence

- 机检三门全绿：`check_01b_rawtext` PASS、阶段 1 回归 32/32、契约校验 C1–C12 PASS；95 行引文（含组行）全部首尾落原文边界。

## [repo/v1.7.16] - 2026-10-19

> 施工清单 A3 首批：`01b` 第五章 7.施工质量要求 7.1 设计的质量保证要求（P4505–P4570）43 行入库（sp-910–952）——7.施工质量要求进入分批全量（余 7.2 设备采购/7.3 土建安装调试/7.4 设备监造及验收挂起）。① 随 bump 0.15.0（见 `bid-response-plan/v0.15.0`）。

### Changed

- `skills/bid-response-plan/scripts/parse_spec_items.py`：SPEC_ITEMS 追加 43 行（A3a=7.1：7.1.1 概述 1＋7.1.2 管理体系 3＋7.1.3 对设计的监督与管理 39）；docstring 覆盖状态由「挂起 2 节」改为「已全量 7 节＋部分全量 1 节（7）＋挂起 1 节（9）」，`SOURCE.page_range`、`main()` 提示语同步。拆分登记——7.1.1 概述引言 P4508、7.1.3 内「1）设计和开发的策划」–「8）设计外包」及「评审活动/设计评审的主要内容」等纯主题标号段不抽（照 4.8.2 先例），其下正文义务段逐段抽；设计输入（1）–（5）、设计评审内容三组 a/b/c/d 共 12 项逐条。
- `tests/check_01b_rawtext.py` 硬编码计数行同步（部分 7.施工质量 43，sp-910–952）。
- `skills-lock.json`（`--write-lock`）：① 0.15.0。

### Evidence

- `check_01b_rawtext` PASS（952 行引文与 `full_dump.txt` 逐行一致）；阶段 1 回归 32/32；契约校验 C1–C12 PASS（锁内 ① 0.15.0）。
- 产物再生 `workdir/acceptance/bid_base/01b_spec-items.json`：952 条，stdlib 结构自检逐键符合（本机无 jsonschema，降级口径已登记）。

## [bid-response-plan/v0.15.0] - 2026-10-19

> ① `01b` 第五章 7.施工质量要求分批全量首批（A3a）：新增 7.1 设计的质量保证要求 43 行（sp-910–952）。

### Added

- 7.1 设计的质量保证要求 43 行（sp-910–952）：
  - 7.1.1 概述 1 行：设计质保要求传递与记录文件保管提交。
  - 7.1.2 设计单位管理体系要求 3 行：ISO9001 体系建立与运行／管理体系证书及手册/程序清单提交／资料资质证件清单建档备案。
  - 7.1.3 对设计的监督与管理 39 行：1）策划（系统设计方案总体策划审批／内容组行／修改程序与更改记录）＋2）输入（（1）–（5）逐条＋输入清单与评审记录提交）＋3）输出（输出文件整理审批备案）＋4）评审（评审活动 2＋设计评审内容三组 a/b/c/d 共 12 项逐条）＋5）设计验证（组织与目的／方法（1）–（3）／记录报告提交）＋6）设计确认（方式（1）–（4）／承包人参与及提前 1 周通知）＋7）设计更改（审批过程／触发情形与反馈／更改手续 a/b/c）＋8）设计外包（禁止转包和再次分包）。

### Changed

- `SKILL.md` frontmatter 0.14.0→0.15.0＋版本史行；docstring 覆盖状态/拆分登记；`SOURCE.page_range`、`main()` 提示语、`tests/check_01b_rawtext.py` 计数行同步。

### Evidence

- 机检三门全绿：`check_01b_rawtext` PASS、阶段 1 回归 32/32、契约校验 C1–C12 PASS；43 行引文（含组行）全部首尾落原文边界。

## [repo/v1.7.15] - 2026-10-19

> 施工清单 A2 收官：`01b` 第五章 4.施工安装要求 4.9 工程质量验收规程、规范（P4404–P4477）2 行入库（sp-908–909）——4.1–4.9 累计 571 行，**4.施工安装要求全节完成**（第五章已全量 7 节，余 7.施工质量/9.工程管理挂起）。① 随 bump 0.14.0（见 `bid-response-plan/v0.14.0`）。

### Changed

- `skills/bid-response-plan/scripts/parse_spec_items.py`：SPEC_ITEMS 追加 2 行（4.9 P4405–P4476 为 72 项标准清单，同质并列无独立可核验值→按组 1 行 sp-908，照 sp-084 规范清单组/sp-196/198 资料组行先例，锚点注首末段 P4405；P4476；P4477 兜底条款→单独 1 行 sp-909，照 sp-085 先例）；docstring 覆盖状态由「已全量 6 节＋部分全量 1 节」改为「已全量 7 节」，4.施工安装尾注并入已全量清单（569→571 行，sp-339–907→sp-339–909），`SOURCE.page_range`、`main()` 提示语同步。
- `tests/check_01b_rawtext.py` 硬编码计数行同步（4.施工安装571，sp-339–909；去「部分」）。
- `skills-lock.json`（`--write-lock`）：① 0.14.0。

### Evidence

- `check_01b_rawtext` PASS（909 行引文与 `full_dump.txt` 逐行一致）；阶段 1 回归 32/32；契约校验 C1–C12 PASS（锁内 ① 0.14.0）。
- 产物再生 `workdir/acceptance/bid_base/01b_spec-items.json`：909 条，stdlib 结构自检逐键符合（本机无 jsonschema，降级口径已登记）。

## [bid-response-plan/v0.14.0] - 2026-10-19

> ① `01b` 第五章 4.施工安装要求收官（A2j）：新增 4.9 工程质量验收规程、规范 2 行（sp-908–909），4.施工安装要求全节完成。

### Added

- 4.9 工程质量验收规程、规范 2 行（sp-908–909）：
  - sp-908 规程规范清单组：P4405–P4476 共 72 项现行国家/行业质量验收规程、规范（含风电达标投产验收/陆上风电场施工安装/风电验收、GB502xx 建筑与结构、GB501xx 电气装置安装、DL5009.1~3 电力建设安全、110kV~750kV 架空输电线路、钢结构焊接/防腐蚀、给排水、通信线路等），同质并列无独立可核验值按组 1 行（首末锚点 P4405；P4476）。
  - sp-909 兜底条款：P4477「以上条目若有新的版本，则执行新版本。以上条目的标准不一致时，则执行高标准。以上条目未涵盖的部分，由招标人和监理协商确定参照国内相关标准。」单独 1 行。

### Changed

- `SKILL.md` frontmatter 0.13.0→0.14.0＋版本史行；docstring 覆盖状态/尾注；`SOURCE.page_range`、`main()` 提示语、`tests/check_01b_rawtext.py` 计数行同步。

### Evidence

- 机检三门全绿：`check_01b_rawtext` PASS、阶段 1 回归 32/32、契约校验 C1–C12 PASS；2 行引文（组行首末锚点＋兜底整段）全部首尾落边界。

## [repo/v1.7.14] - 2026-10-19

> 施工清单 A2 续批落地：`01b` 第五章 4.施工安装要求 4.8 安全文明施工（P4328–P4403）45 行入库（sp-863–907）——4.1–4.8 累计 569 行，余 4.9 工程质量验收规程规范仍挂起。① 随 bump 0.13.0（见 `bid-response-plan/v0.13.0`）。

### Changed

- `skills/bid-response-plan/scripts/parse_spec_items.py`：SPEC_ITEMS 追加 45 行（4.8.1 承包人的安全保护责任 8＋4.8.2 安全措施 37）；docstring 覆盖状态部分全量 524→569 行，`SOURCE.page_range` 与 `main()` 提示语同步；拆分口径登记——4.8.2（2）–（12）纯主题标号段不抽（照 4.4.8 P4193「1）地面与楼面工程」先例），措施费 1）–17）为异质义务动作逐条，手册内容 1）–18）同质并列且无独立可核验值按组 1 行（照 sp-196/sp-198 先例）；坑登记补充 P4336 句末无句号照录。
- `tests/check_01b_rawtext.py` 硬编码计数行同步（4.施工安装569（部分，sp-339–907））。
- `skills-lock.json`（`--write-lock`）：① 0.13.0。

### Evidence

- `check_01b_rawtext` PASS（907 行引文与 `full_dump.txt` 逐行一致）；阶段 1 回归 32/32；契约校验 C1–C12 PASS（锁内 ① 0.13.0）。
- 产物再生 `workdir/acceptance/bid_base/01b_spec-items.json`：907 条，stdlib 结构自检逐键符合（本机无 jsonschema，降级口径已登记）。

## [bid-response-plan/v0.13.0] - 2026-10-19

> ① `01b` 第五章 4.施工安装要求续批（A2i）：新增 4.8 安全文明施工 45 行（sp-863–907）。

### Added

- 4.8 安全文明施工 45 行（sp-863–907）：
  - 4.8.1 承包人的安全保护责任 8 行：安全生产体系与责任制／安全第一预防为主综合治理方针／安全保护职责与施工安全措施文件报审（28 天）／安全生产宣传教育培训（三级教育、特种作业持证）／遵守安全规程与事故报告（2h 事故快报）／危险作业安全管理机构／安全标准化与劳动保护／接受安全检查与整改考核。
  - 4.8.2 安全措施 37 行：安全措施组成、安全文明施工措施费定义；措施费用途 1）–17）（体系建立/管理制度/责任制/教育培训/现场安全设施/安全会议/技术措施与安全交底/特种设备与特种作业人员/检查与隐患排查治理/安全性评价与危险源/劳动防护与职业健康/应急管理/外包工程/事故报告调查处理/达标投产与标准化/考核与奖惩/其他费用，异质逐条）；措施费使用依据；专项安全技术措施（危大工程专项措施、超规模专家评审）；劳动保护用品发放、安全帽等个人防护用品配置；照明安全、接地及避雷装置、有害气体控制；火工材料存放和运输、工地油库布置修建运行；爆破作业安全措施、电引爆特殊安全装置；消防；洪水和气象灾害防护、防汛抗灾组织分工；信号装置、信号装置维修保护；安全防护手册编制与提交（28 天）；安全防护手册内容 1）–18）同质并列且无独立可核验值按组 1 行（锚点 P4386；P4403）。
  - 未抽项（衔接拆分口径 v2.1 ⑥，不抽）：4.8.2 中（2）专项安全技术措施／（3）劳动保护／（4）照明安全／（5）接地及避雷装置／（6）有害气体的控制／（7）炸药、雷管和油料的存放和运输（若有）／（8）爆破（若有）／（9）消防／（10）洪水和地质灾害、气象灾害的防护／（11）信号／（12）安全防护手册 为纯主题标号段（无独立可核验值），其正文段逐段抽。

### Changed

- `SKILL.md` frontmatter 0.12.0→0.13.0＋版本史行；docstring 覆盖状态/坑登记；`SOURCE.page_range`、`main()` 提示语、`tests/check_01b_rawtext.py` 计数行同步。

### Evidence

- 机检三门全绿：`check_01b_rawtext` PASS、阶段 1 回归 32/32、契约校验 C1–C12 PASS；45 行引文（含组行首末锚点）全部首尾落边界。

## [repo/v1.7.13] - 2026-10-18

> 施工清单 A2 续批落地：`01b` 第五章 4.施工安装要求 4.5 施工组织＋4.6 环境保护与水土保持＋4.7 劳动安全与工业卫生（P4264–P4327）44 行入库（sp-819–862）——4.1–4.7 累计 524 行，余 4.8/4.9 挂起。① 随 bump 0.12.0（见 `bid-response-plan/v0.12.0`）。注：⓪ 本轮前已由并行会话 bump 至 1.5.1（非本轮改动，lock 已一致）。

### Changed

- `skills/bid-response-plan/scripts/parse_spec_items.py`：SPEC_ITEMS 追加 44 行（4.5 施工组织 17＋4.5.2 施工总布置 3＋4.5.3 混凝土 1＋4.5.4 施工用电用水 1＋4.5.5 施工总进度 5＋4.6 环保水保 10＋4.7 劳动安全 7）；docstring 覆盖状态部分全量 480→524 行，`SOURCE.page_range` 与 `main()` 提示语同步；坑登记补充 P4308 工期日期与 1.1 工期目标自相矛盾。
- `tests/check_01b_rawtext.py` 硬编码计数行同步（4.施工安装524（部分，sp-339–862））。
- `skills-lock.json`（`--write-lock`）：① 0.12.0。

### Evidence

- `check_01b_rawtext` PASS（862 行引文与 `full_dump.txt` 逐行一致）；阶段 1 回归 32/32；契约校验 C1–C12 PASS（锁内 ① 0.12.0）。
- 产物再生 `workdir/acceptance/bid_base/01b_spec-items.json`：862 条，stdlib 契约逐键符合（本机无 jsonschema，降级口径已登记）。

## [bid-response-plan/v0.12.0] - 2026-10-18

> ① `01b` 第五章 4.施工安装要求续批（A2h）：新增 4.5–4.7 共 44 行（sp-819–862）。

### Added

- 4.5 施工组织 27 行：4.5.1 施工条件（自然条件/工程条件/突出特点/场地条件/物资/施工特点，描述性 no_negative=False 居多）、4.5.2 施工总布置 3、4.5.3 混凝土（商品混凝土）1、4.5.4 施工用电用水 1、4.5.5 施工总进度 5（含机组安装 3~5d/台、并网/移交/竣工日期——与 1.1 工期目标矛盾，照录登记）。
- 4.6 环境保护与水土保持 10 行：严格执行环评水保批复、环保措施五方面、水保设计原则、三同时、水土流失防治 8 项要求、专项设计与验收、缺陷责任期环境、通报监督、监测/监理委托。
- 4.7 劳动安全与工业卫生 7 行：方针与防范措施、组织机构、两级机构、管理点、规章制度制定/执行/检查。

### Changed

- `SKILL.md` frontmatter 0.11.0→0.12.0＋版本史行；docstring 覆盖状态/坑登记；`SOURCE.page_range`、`main()` 提示语、`tests/check_01b_rawtext.py` 计数行同步。

### Evidence

- 机检三门全绿：`check_01b_rawtext` PASS、阶段 1 回归 32/32、契约校验 C1–C12 PASS；44 行引文全部首尾落边界。

## [repo/v1.7.12] - 2026-10-18

> 施工清单 A2 续批落地：`01b` 第五章 4.施工安装要求 4.4 土建技术标准（P4073–P4263）128 行入库（sp-691–818）——4.1–4.4 累计 480 行，余 4.5–4.9 挂起。① 随 bump 0.11.0（见 `bid-response-plan/v0.11.0`）。

### Changed

- `skills/bid-response-plan/scripts/parse_spec_items.py`：SPEC_ITEMS 追加 128 行（4.4.1 风机基础 9＋4.4.2 道路及吊装平台 43＋4.4.3 升压站布置 2＋4.4.4 采暖通风/给排水 12＋4.4.7 集电线路土建 1＋4.4.8 升压站土建 52＋4.4.9 钢结构 7＋4.4.10 检测验收 2；含表 T37 逐行）；docstring 覆盖状态部分全量 352→480 行，`SOURCE.page_range` 与 `main()` 提示语同步；坑登记补充 4.4.5/4.4.6 编号空缺、两个 4.4.4 重号。
- `tests/check_01b_rawtext.py` 硬编码计数行同步（4.施工安装480（部分，sp-339–818））。
- `skills-lock.json`（`--write-lock`）：① 0.11.0。

### Evidence

- `check_01b_rawtext` PASS（818 行引文与 `full_dump.txt` 逐行一致）；阶段 1 回归 32/32；契约校验 C1–C12 PASS（锁内 ① 0.11.0）。
- 产物再生 `workdir/acceptance/bid_base/01b_spec-items.json`：818 条，stdlib 契约逐键符合（本机无 jsonschema，降级口径已登记）。

## [bid-response-plan/v0.11.0] - 2026-10-18

> ① `01b` 第五章 4.施工安装要求续批（A2g）：新增 4.4 土建技术标准 128 行（sp-691–818）。

### Added

- 4.4 土建技术标准 128 行（sp-691–818）：
  - 4.4.1 风机基础 9 行：工程规模/设计级别/结构安全等级/抗震等级/基础方案（承台 5.1m 三节、760m³、Ca40、P6、预制管桩）/排水。
  - 4.4.2 道路及吊装平台 43 行：设计原则 6、设计范围、场内道路（30.3km）、平面设计（R<80m 外侧 8m 无障碍）、纵断面 7 指标、横断面、路基（边坡/填料 CBR/压实度）、路面、加宽、表 T37 坡长、最小坡长、桥涵（汽20-挂100）、筑路材料、环保、排水沟、施工难点、吊装平台（50m×70m）、安全护栏/警示设施/安全桩/交通标志。
  - 4.4.3 升压站布置 2 行：组成与标高 19.50m、道路与分区。
  - 4.4.4 采暖通风/给排水 12 行：采暖（电暖器）、通风（12 次/h）、空调、给水（DN100/10m³/h/0.20MPa）、排水（分流制/事故油池 100%/雨水泵站/PE 管）。
  - 4.4.7 集电线路土建 1 行：地埋加架空/大开挖基础。
  - 4.4.8 升压站土建 52 行：建筑物装修（综合楼/屋面防水Ⅰ级/辅助用房/立面/围墙/地面楼面/门窗/装饰装修/屋面/防腐蚀/给排水/电气照明/通风空调/标志标识）。
  - 4.4.9 钢结构 7 行：原材料/全数检查/高强螺栓试验与施拧/安装前验收/变形矫正/允许偏差。
  - 4.4.10 检测验收 2 行：土建施工质量/第三方检测。

### Changed

- `SKILL.md` frontmatter 0.10.0→0.11.0＋版本史行；docstring 覆盖状态/坑登记；`SOURCE.page_range`、`main()` 提示语、`tests/check_01b_rawtext.py` 计数行同步。

### Evidence

- 机检三门全绿：`check_01b_rawtext` PASS、阶段 1 回归 32/32、契约校验 C1–C12 PASS；128 行引文全部首尾落边界。

## [repo/v1.7.11] - 2026-10-18

> 施工清单 A2 续批落地：`01b` 第五章 4.施工安装要求 4.3.7 消防工程（P4027–P4072）33 行入库（sp-658–690）；4.3.6 储能系统（不涉及）不抽。4.1–4.3.5＋4.3.7 累计 352 行，余 4.4–4.9 挂起。① 随 bump 0.10.0（见 `bid-response-plan/v0.10.0`）。

### Changed

- `skills/bid-response-plan/scripts/parse_spec_items.py`：SPEC_ITEMS 追加 33 行（4.3.7 消防工程）；docstring 覆盖状态部分全量 319→352 行，`SOURCE.page_range` 与 `main()` 提示语同步；坑登记补充 P4053–P4057 段首项目符号 U+F06C。
- `tests/check_01b_rawtext.py` 硬编码计数行同步（4.施工安装352（部分，sp-339–690））。
- `skills-lock.json`（`--write-lock`）：① 0.10.0。

### Evidence

- `check_01b_rawtext` PASS（690 行引文与 `full_dump.txt` 逐行一致）；阶段 1 回归 32/32；契约校验 C1–C12 PASS（锁内 ① 0.10.0）。
- 产物再生 `workdir/acceptance/bid_base/01b_spec-items.json`：690 条，stdlib 契约逐键符合（本机无 jsonschema，降级口径已登记）。

## [bid-response-plan/v0.10.0] - 2026-10-18

> ① `01b` 第五章 4.施工安装要求续批（A2f）：4.3.6 储能（不涉及）不抽，新增 4.3.7 消防工程 33 行（sp-658–690）。

### Added

- 4.3.7 消防工程 33 行（sp-658–690）：消防设计法规与方针、消防给水与灭火装置（生活舱<300m2不设消防给水、排油注氮）、新技术应用、消防设备标准（GB50229/GB50140/DL5027）、消防体系与总体布置、综合消防技术措施、总体布置防火、电气设备防火与消防道路、主变/电气房间灭火器配置、风机火灾探测报警与自动灭火、阻燃电缆与电缆通道防火（分层敷设/孔洞封堵/阻火墙部位 5 项/阻燃豁免/非阻燃明敷防护）、电气房间消防与烟感、环形消防道路、建筑间距、电缆防火分隔、消防电源双回路、灭火器选型、火灾自动报警系统（GB50116）。

### Changed

- `SKILL.md` frontmatter 0.9.0→0.10.0＋版本史行；docstring 覆盖状态/坑登记；`SOURCE.page_range`、`main()` 提示语、`tests/check_01b_rawtext.py` 计数行同步。

### Evidence

- 机检三门全绿：`check_01b_rawtext` PASS、阶段 1 回归 32/32、契约校验 C1–C12 PASS；33 行引文全部首尾落边界（含 U+F06C 项目符号段）。

## [repo/v1.7.10] - 2026-10-18

> 施工清单 A2 续批落地：`01b` 第五章 4.施工安装要求 4.3.5 升压站主要设备（P3771–P4024，含表 T33/T34/T35/T36 逐行）185 行入库（sp-473–657）——4.1–4.3.5 累计 319 行，余 4.3.6–4.9 挂起。① 随 bump 0.9.0（见 `bid-response-plan/v0.9.0`）。

### Changed

- `skills/bid-response-plan/scripts/parse_spec_items.py`：SPEC_ITEMS 追加 185 行（4.3.5：电气一次 71 行＋电气二次 114 行；表 T33 9＋T34 11＋T35 6＋T36 6 逐行）；docstring 覆盖状态部分全量 134→319 行，`SOURCE.page_range` 与 `main()` 提示语同步；跨段坑登记（P3832 跨 P3833、P3858 跨 P3859、P3981 跨 P3982 均省略号照录）。
- `tests/check_01b_rawtext.py` 硬编码计数行同步（4.施工安装319（部分，sp-339–657））。
- `skills-lock.json`（`--write-lock`）：① 0.9.0。

### Evidence

- `check_01b_rawtext` PASS（657 行引文与 `full_dump.txt` 逐行一致；表 T 行含制表符单元格边界、跨段省略号）；阶段 1 回归 32/32；契约校验 C1–C12 PASS（锁内 ① 0.9.0）。
- 产物再生 `workdir/acceptance/bid_base/01b_spec-items.json`：657 条，stdlib 契约逐键符合（本机无 jsonschema，降级口径已登记）。

## [bid-response-plan/v0.9.0] - 2026-10-18

> ① `01b` 第五章 4.施工安装要求续批（A2e）：新增 4.3.5 升压站主要设备 185 行（sp-473–657）。

### Added

- 4.3.5 升压站主要设备 185 行（sp-473–657）：
  - 1）电气一次部分 71 行（sp-473–543）：主变 SZ20-100000/220kV 参数 5 行、220kV GIS、表 T33（出线GIS断路器/隔离开关/接地开关/CT/母线/套管、电压互感器、避雷器）9 行、35kV 开关柜与 SVG、表 T34（开关柜断路器/隔离手车/接地开关/CT/避雷器/电压互感器、接地变兼站用变、SVG）11 行、站用变参数、导体与电缆、表 T35 6 行、绝缘子、高压开关柜（1）–（13）、低压开关柜（1）–（7）、35kV 侧接地方式（跨 P3833 省略号）。
  - 2）电气二次部分 114 行（sp-544–657）：线路/母线/35kV 母线保护、故障录波与表 T36、保护信息子站、故障解列、主变保护、35kV 保护、二次线、监控系统、测量、同步时钟、PMU、电能质量、直流/UPS、火灾报警、安防/视频/门禁、调度关系、遥测量 12＋遥信量 13、远动传输、调度数据网、安全防护、远动系统、电能计量、有功无功、功率预测、网厂交互、安全评估、惯量响应与一次调频（跨 P3982）、同步相量、通信部分通道。

### Changed

- `SKILL.md` frontmatter 0.8.0→0.9.0＋版本史行；docstring 覆盖状态/跨段坑登记；`SOURCE.page_range`、`main()` 提示语、`tests/check_01b_rawtext.py` 计数行同步。

### Evidence

- 机检三门全绿：`check_01b_rawtext` PASS、阶段 1 回归 32/32、契约校验 C1–C12 PASS；185 行引文全部首尾落边界（含表 T 行制表符单元格边界与跨段省略号）。

## [repo/v1.7.9] - 2026-10-18

> 施工清单 A2 第一批落地：`01b` 第五章 4.施工安装要求按**小节**分批全量（A2a–A2d）——4.1 设备采购、4.2 工程施工、4.3.1 概述、4.3.2 风力发电机组、4.3.3 塔筒、4.3.4 箱变共 134 行（sp-339–472）；4.3.5–4.9 仍挂起。① 随 bump 0.8.0（见 `bid-response-plan/v0.8.0`）。

### Changed

- `skills/bid-response-plan/scripts/parse_spec_items.py`：SPEC_ITEMS 追加 134 行（4.1 设备采购 5＋4.2 工程施工 18＋4.3.1 概述 10＋4.3.2 风力发电机组 22＋4.3.3 塔筒 39＋4.3.4 箱变 40）；docstring 覆盖状态新增「部分全量」类（4.施工安装要求按小节登记，余 4.3.5–4.9 挂起），`SOURCE.page_range` 与 `main()` 提示语同步；原文坑登记（P3673 编号项「8）」误用 Heading 2、P3681 样式字段被误抽、P3692–P3699 样式「段」、P3706–P3708「Normal_7」、P3721「Body Text」——均照录不改）。
- `tests/check_01b_rawtext.py` 硬编码计数行同步（4.施工安装134（部分）；挂起 7/9 节）。
- `skills-lock.json`（`--write-lock`）：① 0.8.0。

### Evidence

- `check_01b_rawtext` PASS（472 行引文与 `full_dump.txt` 逐行一致）；阶段 1 回归 32/32；契约校验 C1–C12 PASS（锁内 ① 0.8.0）。
- 产物再生 `workdir/acceptance/bid_base/01b_spec-items.json`：472 条，stdlib 契约逐键符合（本机无 jsonschema，降级口径已登记）。

## [bid-response-plan/v0.8.0] - 2026-10-18

> ① `01b` 第五章 4.施工安装要求按小节分批全量（A2a–A2d）：新增 134 行（sp-339–472）。

### Added

- 4.1 设备采购 5 行（sp-339–343）：采购范围总述＋风机塔筒平移合同与分界点＋催交运输仓储＋保管储存＋备品备件 0.5%。
- 4.2 工程施工 18 行（sp-344–361）：4.2.1 土建工程编号项 1）–13）逐条 13 行＋4.2.2 设备安装（风电场内/升压站内范围、采购全流程、标识标牌、吊装载荷≤80%）5 行。
- 4.3.1 概述 10 行（sp-362–371）：装机规模/出口电压/集电线路/电缆/接地网/升压站设计/无功补偿/监控/继电保护/图像监控（描述性 no_negative=False）。
- 4.3.2 风力发电机组 22 行（sp-372–393）：选型原则、风机类型、寿命25年、温度、IEC、可靠性、可利用率≥98%/≥96% 及扣款/更换、功率曲线保证值≥96% 与违约金、备品备件、安全带 10 套、可利用率与功率曲线保证值。
- 4.3.3 塔筒 39 行（sp-394–432）：钢混塔筒组成、样式设计、内附件/电气系统、法兰 Q345E、标识、监测技术、设计细则、防腐 20 年、锚栓板厚 Q355/C80、防坠落/照明/插座等。
- 4.3.4 箱变 40 行（sp-433–472）：结构/通风温升、开关柜五防、防护 IP65、寿命 25 年、接线端子、接地、焊接、外壳、运输存放、阻燃/连锁/进线/绕组铜质、UPS 2 小时、双环网、能效 GB20052 二级、自动灭火等。

### Changed

- `SKILL.md` frontmatter 0.7.0→0.8.0＋版本史行；docstring 覆盖状态/坑登记；`SOURCE.page_range`、`main()` 提示语、`tests/check_01b_rawtext.py` 计数行同步。

### Evidence

- 机检三门全绿：`check_01b_rawtext` PASS、阶段 1 回归 32/32、契约校验 C1–C12 PASS；134 行引文全部首尾落边界。

## [repo/v1.7.8] - 2026-10-18

> 施工清单 A1 落地：`01b` 第五章 1.总则节（P3229–P3332）全量拆行，101 行入库（sp-238–338）——第五章已全量 6 节（1/2/3/5/6/8），挂起收窄至 3 节（4/7/9）。① 随 bump 0.7.0（见 `bid-response-plan/v0.7.0`）。

### Changed

- `skills/bid-response-plan/scripts/parse_spec_items.py`：SPEC_ITEMS 追加 101 行（1.1 基本要求与建设目标 21＋1.2 工作界区 48＋1.3 工程概况 32）；docstring 覆盖状态 1.总则 移入已全量并登记原文坑（正文误用 Heading 4＝P3299/P3303–P3320、Body Text＝P3271/P3274、引言二级条标题＝P3288、孤立编号 P3269「2）」/P3270「3）」/P3320「9）」（无 1–8）、P3245 疑漏标点、P3305/P3327「。。」双句号——全部照录不改）；`SOURCE.page_range` 与 `main()` 提示语同步为已全量 6 节/挂起 3 节。
- `tests/check_01b_rawtext.py` 硬编码计数行同步（1.总则101＋…；挂起 4/7/9 节）。
- `skills-lock.json`（`--write-lock`）：① 0.7.0。

### Evidence

- `check_01b_rawtext` PASS（338 行引文与 `full_dump.txt` 逐行一致，含日期不规则空格片段、内联（1）–（16）编号项、a./b. 供货范围长引文、弯曲引号组行）；阶段 1 回归 32/32（R4-1 引文照录、R5 合成派生均不受影响）；契约校验 C1–C12 PASS（锁内 ① 0.7.0）。
- 产物再生 `workdir/acceptance/bid_base/01b_spec-items.json`：338 条，id sp-001–338 连续唯一；stdlib 契约逐键符合（doc＋item 层，`additionalProperties=false`；unit/tolerance 空串系 schema 注明口径）。本机未装 `jsonschema`，走结构自检口径（与 `validate_plan.py` 降级行为一致）。

## [bid-response-plan/v0.7.0] - 2026-10-18

> ① `01b` 分阶段全量第四批：新增第五章 1.总则 101 行（sp-238–338）。

### Added

- 1.1 基本要求与建设目标 21 行（sp-238–258）：义务段 7＋工期 4 日期拆行（开工 2025-07-01／并网 2026-06-30／移交 2026-07-30／竣工验收 2026-09-30）＋安全/文明施工/环保/五个零按组 1 行＋职业健康/优质工程/质量目标（合格率 100%×2，unit `%`）/投资控制。
- 1.2 工作界区 48 行（sp-259–306）：设计 9（含（1）–（5）内联编号项逐条）＋采购 6（含 a./b. 风机塔筒供货范围长引文两行、平移合同与分界点）＋施工 7（（1）–（4）内联）＋调试验收 2＋征租地 5（P3267 长段＋P3269/P3270 孤立编号照录）＋送出 1＋协调 1＋费用 1＋1.2.9 编号项（1）–（16）16 行。
- 1.3 工程概况 32 行（sp-307–338）：地理位置/规模参数（no_negative=False，描述性）2＋气象 1＋风能资源 8（含测风塔满年复核义务 True、IECⅢ类选型 True）＋工程地质 10（含基底防水植被恢复 True）＋总体方案 11（设计参数照录，True）。

### Changed

- `SKILL.md` frontmatter 0.6.0→0.7.0＋版本史行；docstring 覆盖状态/坑登记；`SOURCE.page_range`、`main()` 提示语、`tests/check_01b_rawtext.py` 计数行同步。

### Evidence

- 机检三门全绿：`check_01b_rawtext` PASS、阶段 1 回归 32/32、契约校验 C1–C12 PASS；101 行引文全部首尾落边界（BOUND/SENT_END/段首段尾），无省略号静默截断。

## [repo/v1.7.7] - 2026-10-18

> 施工清单 B-附 P1 经拍板（选项 3：先 P1 后施工）落地：schema「同版本同内容冻结」纪律机检化（`validate_contract` 新增 **C12**），堵住 63 处漂移的共性根因（结构性变更在 `0.4` 版内静默发布、旧产物与坏产物机器无法区分）。设计级改动，计划书同步修订。

### Added

- `tests/validate_contract.py` **C12**：lock 内每个共用 schema 绑定 `(schema_version, hash)`——版本实读 `properties.schema_version.const`（JSON）／顶层 `schema_version:` 行（YAML）；**同版本异内容**即报错，且 `--write-lock` **拒绝盲写**（写锁路径 compare=False 对内容变更原本零感知，即静默变更通道）；bump 版本后才允许更新基线；无 const 声明报错（无法绑定）；双字段（`schema_version`/`contract_schema_version` const）一致性校验；内嵌 3 组合成样例自证检测器（抓同版本异内容／不误杀 bump 改版／不误杀同版本同内容）——负例永久回归。旧 lock 无版本字段时提示 `--write-lock` 补齐。
- 计划书 §3.8「schema 内容冻结」条、§B.2「schema 冻结」校验行、§0.0 v0.16 修订登记（版本内修订，不另起版本号）。

### Fixed（P1 连带发现的同类版本失忆）

- `compliance-report.schema.json` 的 `schema_version` 原为 loose `{"type":"string"}`：实装 `check_compliance.py` 写 `0.2`、示例市真实产物实读 `0.2`、fixture 却写 `0.1`——各说各话而无任何检查看得见。补 `const "0.2"`，fixture `06_compliance.sample.json` 同步 `0.1`→`0.2`（fixture 键序与实装输出逐键一致，仅版本串滞后）。② 随 bump 0.3.3（见 `bid-compliance-check/v0.3.3`）。
- `docs/v0.16_阶段1收口施工清单.md` B-附 由「待拍板」转「已拍板实施」（历史 0.4 静默变更不回溯改版，产物侧仍由 B1–B4 修）；`AGENTS.md` C1–C11→C1–C12＋硬约定补冻结条款。

### Changed

- `skills-lock.json`（`--write-lock` 再生，`_scope`/`_intentional_excludes` 保留）：② 0.3.3、`compliance-report.schema.json` hash 更新、9 个 schema 各补 `schema_version` 字段（0.1×5＝metadata/facts/spec-items/business-forms/outline，0.2×3＝bid-plan/format-outline/compliance-report，0.4×1＝tender-facts）。
- 安装副本 `~/.workbuddy/skills/bid-compliance-check/` 三文件字节同步至 0.3.3（SKILL.md／compliance-report.schema.json／check_compliance.py——后者连带对齐 repo/v1.7.2 的 F 类文案修复，安装副本此前停留在 repo/v1.7.1 时点）；安装目录内另有嵌套重复包 `bid-compliance-check\bid-compliance-check\`（历史误拷，非技能加载路径），本轮未动。

### Evidence（负例现场实测）

- 基线写入后探针：篡改 `compliance-report.schema.json`（同版本换内容）→ validate **FAIL**（`[C2]` 通用失配＋`[C12]` 点名"同版本(0.2)异内容"，exit=1）→ `--write-lock` **拒绝**（exit=1、lock 字节未变）→ 还原后 validate PASS（exit=0，源文件哈希字节级复原）。内嵌自证随每次 validate 运行。
- 规则语义：机器无法区分「纯可选字段追加」与结构性变更，故取**任何内容变更必须 bump `schema_version`**（宁严勿松），semver 档位由人判断。

## [bid-compliance-check/v0.3.3] - 2026-10-18

> ② 补 schema 版本绑定（配套 repo/v1.7.7 C12 冻结基线）：`compliance-report.schema.json` 声明 `const schema_version="0.2"`，根治 loose string 下实装/样例版本各说各话不可见。

### Changed

- `assets/compliance-report.schema.json`：`schema_version` `{"type":"string"}`→`{"const":"0.2"}`（依据：`check_compliance.py` L464 写 0.2、示例市 `bid/06_compliance/compliance-report.json` 实读 0.2、schema 描述"随 ② v0.2.0 落地"；mini_schema 支持 const，C5 实测过）。
- `SKILL.md` frontmatter 0.3.2→0.3.3＋版本史行；根 `README.md` 版本表同步；安装副本三文件字节同步（0.3.3）。
- `tests/fixtures/06_compliance.sample.json`：`schema_version` `0.1`→`0.2`（对齐实装与真实产物；repo 源 `check_compliance.py` 本轮未改逻辑）。

## [repo/v1.7.6] - 2026-10-18

> 施工清单补记 63 处漂移共性根因的处置建议（待拍板，纯文档，无技能版本变更）。

### Added

- `docs/v0.16_阶段1收口施工清单.md` B 系列附条（**B-附**）：登记 P1 建议——"非纯可选字段追加的 schema 结构性变更必须 bump `contract_schema_version`"。根因：结构性变更（`clarifications` 字符串→对象、枚举扩缩、required 变化）在 0.4 版内静默发布，旧产物与坏产物机器无法区分。**未实施**；若拍板，落点＝计划书 §3.8/§B.2＋`validate_contract` 新增检查项（设计级改动）。自扫 `scan_doc --note` PASS。

## [repo/v1.7.5] - 2026-10-18

> 下一轮工作编写物两件（纯文档，无技能版本变更）。

### Added

- `docs/v0.16_阶段1收口施工清单.md`：阶段 1 收口施工单——A 系列（01b 挂起 4 节全量）、B 系列（63 处漂移清理＋#0/#2 项目级复验，含"52 处 review_stage 禁自动补猜"硬约束）、C 系列（计划书 §11.2 重跑与关闭判据，两轨对账并入）、D 系列（阶段 0 残留平台验证）＋施工顺序与不动项；体例沿 `v0.8施工清单.md`。自扫 `scan_doc --note` PASS。
- `AGENTS.md`：给后续 OpenCode 会话的紧凑指引——必跑三机检＋`--write-lock`、铁律/交接约定/schema 多副本硬约定、数据只读与副本原则、计划书 gitignore 登记惯例、阶段 1 未闭/已闭清单（防重做）。

## [repo/v1.7.4] - 2026-10-18

> N1 回归测试环境耦合修复 + 计划书 §0.0 修订登记（两处净增量，纯测试/文档，无技能版本变更）。

### Fixed

- `tests/test_stage1_regression.py`：`run()` 子进程输出钉死 UTF-8（`env=PYTHONUTF8=1` + `encoding="utf-8", errors="replace"`）。原实现在中文 Windows 默认 locale 下子进程写 GBK、父进程按 utf-8 解码，读线程 `UnicodeDecodeError` → `r.stderr=None` → 断言 `TypeError` 崩溃，须宿主预设 `PYTHONUTF8=1` 才能跑（独立复审 N1，实测复现）。修复后默认编码环境直接 `python tests/test_stage1_regression.py` 32/32 全过。

### Changed

- `docs/投标文件Skill建设计划_v0.16.md`：§0.0 末补「v0.16 修订登记」一段——三脚本取消（repo/v1.7.3）与 §6.2 回填 ⓪ v1.5.0 加权三字段，作为版本内范围修订正式入计划书 §0 变更记录（此前仅 §5 L694 行内注与本 CHANGELOG 有载）。

### Notes

- F 类文案、④ README §8.8.3 四条、顶层 NOTICE 已由 repo/v1.7.2 完成，本轮独立实测确认在位，不重复登记；`截止前` 全仓扫描剩余命中为澄清截止/里程碑截止等正当语境，非 F 类文案残留。

## [repo/v1.7.3] - 2026-10-18

> 计划书 §5 修订：取消 `check_timeliness.py` / `check_similarity.py` / `render_report.py` 三项脚本（本次不实现）。F 类资质时效保留于 `check_compliance.py` 内联（`qual_timing()`）；雷同自查（原 `check_similarity.py`）转为 §8.6 人工核对项；报告渲染保持内联。计划书目录树与 §8.6（防线二 / 平台降级 / 测试场景 / E 类能力行）同步修订；验收记录 L509 将 #8 从待办移除。计划书本身按约定不进版本库（.gitignore）。

## [repo/v1.7.2] - 2026-10-18

> 独立审计（综合审核结论）第一/二档快速修复：F 类文案方向、脚本自述漂移、README 版本表、NOTICE、计划书 §5.2 矛盾、④ README 四要求、prompts 结构占位。纯文本/新建，零逻辑改动。

### Fixed

- `bid-compliance-check/scripts/check_compliance.py`：F 类文案「截止前180天内」→「截止后180天内」（L264/L288），与时效分支逻辑（deadline≤v≤deadline+180）对齐；逻辑不动。
- `bid-response-plan/scripts/parse_spec_items.py`：覆盖状态自述「8 节」→「5 节」、「挂起 3 节」→「挂起 4 节」三处漂移修正。
- `README.md`：技能一览版本表对齐 lock（tender 1.5.0 / delivery 1.1.3 / bid-response 0.6.0 / bid-compliance 0.3.2）。
- `NOTICE`：新增顶层版权/许可声明（计划 §5 L638）。
- `docs/投标文件Skill建设计划_v0.16.md`：§5.2 L788 `compliance-report.schema.json` 进 lock 标记「否」→「是」（计划表格陈旧）。
- `bid-docx-export/README.md`：§8.8.3 操作须知补齐 4 条要求表（时间戳不覆盖/先看页数与目录/人工改过不重跑/修订批注已删）。
- `prompts/templates/README.md`：建立计划要求的 10 模板索引占位（完整内容随阶段 2/3）。

### Notes

- 第三档（② 三脚本新开发、01c↔04 基准、01_tender-facts 重跑、01b 余 4 节、漂移 63 处+§11.2 重跑）另行排期，未含本批。

## [repo/v1.7.1] - 2026-10-18

> 独立审计（换模型交叉验证）整改：B 级（契约矩阵范围声明 + 有意排除注释固化）。A 级（安装副本与仓库源漂移）已同步安装目录，不落仓库。

### Changed

- `skills-lock.json`：新增 `_scope`（声明 in_scope 五技能与 out_of_scope 的 `delivery-audit` / `business-contract-review`）与 `_intentional_excludes`（`knowledge.schema.yaml` 不进 lock 的依据，见验收记录 v0.16），固化审计 B 级发现。
- `tests/validate_contract.py`：`--write-lock` 机器再生时保留 `_` 前缀诊断性元字段（原会被静默抹掉），确保 `_scope` / `_intentional_excludes` 持久。

### Notes

- A 级修复（安装副本 `~/.workbuddy/skills/` 对齐仓库源）不落仓库；旧安装副本备份于 `workdir/backup_install_skills_2026-10-18/`。6 技能（tender-document-review 1.5.0 / bid-response-plan 0.6.0 / bid-compliance-check 0.3.2 / delivery-audit 1.1.3 / bid-technical-proposal 0.1.1 / bid-docx-export 0.1.1）已字节一致同步；business-contract-review 1.0.0 安装与仓库本就一致，未动。

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

## [bid-response-plan/v0.6.0] - 2026-10-18

> ① 01b 第五章分阶段全量第三批（P1-d 续批二）：新增 8.竣工试验与验收 131 行（sp-107–237，含 T39 图纸资料分配表逐行 5 行），第五章已全量 5 节累计 237 行；挂起改 1.总则/4.施工安装/7.施工质量/9.工程管理；组行判定入口径 v2.1。

### Added

- **`01b` 8.竣工试验与验收全量 131 行**（P4892–P5138＋表 T39）：8.1 试验项目 28／8.2 项目验收 34／8.3 标签标识 8／8.4 培训 10／8.5 性能试验 7／8.6 移交资料 9／8.7 缺陷保修 9／8.8 保修范围 1／8.9 文件要求 25（含 T39 管辖段 1＋逐行 5）。
- **拆分口径 v2.1「组行判定」入 docstring**：编号项内容异质→逐条；同质并列且无独立可核验值（≥3 项）→每组一行（requirement 记项数与代表项、锚点注首末项）；带份数/套数/时限/年限/比例/数量或独立标准引用→逐条（T39 逐行、IEC61730-1 单行）；两项并列亦逐条。定义段夹带独立义务的（8.9.3「批准」条之承包人全责）按义务抽一行。
- **原文坑登记**：8.1.6 标题为 Normal 样式（P4921，按 Heading grep 会漏）；8.6.2 标题被原文误编号为 8.5.2（P5048）；8.9.3 术语定义块 P5103–P5115 按定义不抽；docx 填空残片（`_  _`/`__24_`/`_____`）逐字照录。

### Fixed（机检器两处真实缺陷）

- `tests/check_01b_rawtext.py` `load_units()`：T 行原取末列单元格 →「数据在非末列、末列为空」的表格行（示例市 T39）整行不可见。改为拼接全部单元格；再由 `boundary_ok()` 增补**制表符=单元格边界**语义（片段可跨单元格，起止须落边界或标点/段首段尾），修复随之暴露的 T1R10 引文起点前置字符非标点误报。
- `boundary_ok()` 重写时漏做 PUNCT 归一化（半角括号未转全角）→ 一度误报 17 条既有引文；修复为与 `norm()` 同等归一化。

### Tests

- `tests/check_01b_rawtext.py`：237 条引文逐行一致 PASS。
- `test_stage1_regression.py`：**32/32 PASS**（新增 R4-6 四项单元提取、R4-7 两项单元格边界与中英标点等价、R5 两项覆盖口径动态派生）。

## [bid-compliance-check/v0.3.2] - 2026-10-18

> ② 偏离表口径文案改**从 01b JSON 动态派生**，根治「① 每全量一批、② 硬编码计数必漂移一次」（已漂移两次）。

### Added

- `summarize_01b()`：按 clause「第五章\<节号\>」分组计数，派生"已全量 N 节（各节行数；共 M 行）＋挂起节"；节号→节名表只列结构不列计数；01b 缺失时返回 `(None, None)` 由调用方走读取异常分支。

### Fixed

- `check_compliance.py` 局部变量 `summary` 与既有 `summary` 字典同名遮蔽 → 末尾打印 `summary['cross_fatal_no_card']` 崩 TypeError；改名为 `n01b/cov`（实跑 ②-A 复验）。

## [repo/v1.7.0] - 2026-10-18

> 仓库级：验收记录「P1-d 续批二」入档（#1 更新为部分通过 5/9 节）、机检器单元格边界语义定型、`skills-lock.json` 刷新至 ①=0.6.0／②=0.3.2。

### Added

- `docs/v0.16_阶段1验收记录.md` 新增「P1-d 续批二」小节（131 行按节明细、口径 v2.1、原文坑 5 项、机检器两缺陷、机检证据 5 项、#1/#5 影响更新）。

### Changed

- `skills-lock.json`：`bid-response-plan` 0.5.0→0.6.0、`bid-compliance-check` 0.3.1→0.3.2，`generated_at` 刷新。

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
