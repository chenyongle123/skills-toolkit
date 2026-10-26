# AGENTS.md — skills-toolkit

本仓库是 **SKILL.md 技能包内容库**（非代码应用）：五技能投标链 ⓪①②③④ ＋ 两个套件外技能。没有构建系统；正确性由 `tests/` 下的 Python 机检脚本保证（零三方依赖，纯标准库，Python 3.8+）。

## 必跑命令（改动后声称"完成"之前）

```powershell
python tests/validate_contract.py            # 契约闸门：C1–C13（含 C5b/C5c/C13；schema hash与同版本冻结、铁律逐字一致、交接约定一致、版本与 lock 对齐、fixtures、SKILL.lite.md 契约；PyYAML 缺失时 C5b/C5c 跳过并提示）
python tests/test_stage1_regression.py       # 阶段 1 回归 32 项（R1–R5）
python tests/test_stage2_regression.py       # 阶段 2 回归 73 项（T2-1~T2-11：③ v0.3.1 ＋ ②-B v0.5.3）
python tests/test_stage3_regression.py       # 阶段 3 回归 74 项（T3-1~T3-12：④ v0.2.2 导出链＋gate 负例）
python tests/test_stage4_regression.py       # 阶段 4 回归 60 项（T4-1~T4-9：run_acceptance 全链 E2E＋跳步/状态负例＋frontier＋--json＋暗标标识＋**入口闸门 T4-8**＋**②-B 暗标终检 T4-9**）
python tests/test_stage5_regression.py       # 阶段 5 回归 28 项（T5-1~T5-8：SKILL.lite.md ①②③ 契约＋C13 检测器六负例自证）
python tests/test_stage6_regression.py       # 阶段 6 回归 14 项（T6-1~T6-7：select_facts 快照链＋check_facts_library 机检自证；合成母库，不依赖本机路径）
python tests/check_knowledge.py              # 素材母库（knowledge/）机检 K1–K9：结构/契约字段/tags 词表命中/aging 提示；空库绿、有条目后违约 rc=1
python tests/check_facts_library.py --library <企业事实母库>   # 企业事实母库机检 L1–L8（母库在仓库外本地目录，路径本机专用；空库绿）
python tests/scan_doc.py docs/投标文件Skill建设计划_v0.21.md        # 计划书自扫 D1–D6（改计划书必跑）
python tests/scan_doc.py docs/<记录类文档>.md --note               # 记录类文档自扫（--note 跳过 D1 版本解析与 D5 待确认节）
```

顺序不强制（相互独立），但**十一者全绿才算验完**。改了 frontmatter `version` 或 schema 后：

```powershell
python tests/validate_contract.py --write-lock   # 重写 skills-lock.json（保留 `_` 前缀诊断元字段）
```

控制台是中文 GBK：脚本输出中文会乱码但不影响判定。要可读输出加 `$env:PYTHONUTF8='1'`（回归测试的子进程已自钉 UTF-8，无需设置）。

## 硬约定（violate 即 validate_contract 红灯）

- **铁律 8 条**：①—④ 四份 SKILL.md 中**逐字一致**（一字之差即 C3 失败）；⓪ 不复制总则，只在末尾声明受总则约束。
- **四份 `references/流水线交接约定.md`**：字节级一致（C4，比对 sha256）。
- **共用 schema 多副本**（metadata/tender-facts/facts 等）：各技能下副本 hash 必须一致且登记进 `skills-lock.json`；改任一副本 = 改全部副本；**schema 内容任何变更先 bump `schema_version` 再 `--write-lock`**（C12 同版本冻结，同版本换内容的盲写会被拒）。
- **技能包只放运行必需文件**（SKILL.md/README/references/assets/scripts）；开发记录、验收文档、项目个案进 `docs/` 或 `workdir/`，绝不入包。
- **每次技能改动**：bump `SKILL.md` frontmatter `version` ＋ CHANGELOG 条目（技能级 `技能名/vX.Y.Z`，仓库级 `repo/vX.Y.Z`）；版本/锁变化后 `--write-lock`。
- **脚本设计原则**："只报告差异、不自动补猜"——校验失败即非零退出，不得替使用者补齐数据；skills 下脚本零三方依赖（可移植性是产品需求）。

## 数据安全

- `workdir/` 为 gitignored 运行期工作区；**真实项目测试一律在 `workdir/acceptance/` 副本上做**，用户工程目录（如 `<受控项目根>\...`）**全程只读**（验收记录明文的"数据未改动原则"）。
- `tests/check_01b_rawtext.py` 硬编码示例市项目路径 `<受控项目根>\示例发包人示例市100MW风电EPC\src\full_dump.txt`——仅本机可用，换机器需重指路径。

## 容易踩的坑

- **WorkBuddy 运行目录已于 2026-10-26 同步至最新版（勿重做）**：`%USERPROFILE%\.workbuddy\skills\` 此前装载的是旧版（① 0.6.0／② 0.3.3／③ 0.1.1／④ 0.1.1，且①②③ 无 `SKILL.lite.md`），现已同步为 ⓪ v1.5.2／① v0.23.0／② v0.5.3／③ v0.3.1／④ v0.2.2，逐文件 SHA256 差异 0（排除 `__pycache__`）；同时移出三个技能包内的旧版嵌套残留 `<技能名>/<技能名>/`。备份：`<同步备份目录>\`。**重要**：此前的 D1/D2 平台实测结果对当前版本无效；两个装载目录（`.workbuddy\skills` 与 `.config\opencode\skills`）**都要同步**，漏一个即出现"新旧版本并存"。
- **①② 入口闸门已交付（repo/v1.7.36，2026-10-26，勿重做）**：此前直接单脚本调用时缺文件抛 Python traceback，rc 非零、零产物但无产品级提示；现三处入口（`build_bid_plan.gate()`、`check_compliance.gate_a()`、`check_business.gate_a()`）均输出「【执行阻断】→原因→缺少产物→处置」并 rc=2 零产物，形态与 ④ `_common.gate()` 一致，T4-8 十二项固化。**改动入口时勿绕过闸门**，且 `os.makedirs(06_compliance)` 必须在 gate 之后（否则破坏零产物约束）。
- `docs/投标文件Skill建设计划*.md`（计划书）**被 .gitignore 排除**（本地规划稿不公开）：对它的修订以 CHANGELOG `repo/vX.Y.Z` 登记（先例 repo/v1.7.3），并按其 §0 版本变更记录惯例在文内 §0 补登记行。
- **验收记录/CHANGELOG 写的是历史判定，不是当前状态**——仓库常被并行会话推进；动手前先读 CHANGELOG 头部与 `skills-lock.json` 的 `generated_at`，动手后以实跑机检为准，勿凭文档声称"已完成"。
- **阶段 2 已开工（repo/v1.7.24，2026-10-21）**：③ `bid-technical-proposal` v0.2.0 正文能力版完成（chapter.schema + check_facts/word_count 双脚本 + references×5 + 五步循环实装），已镜像运行目录。**勿重做**。
- **企业事实母库＋快照链已交付（repo/v1.7.33，2026-10-21，勿重做）**：用户二次拍板翻转"留待将来"——企业资质**跨项目复用**、母库**放本地不入仓库**（`<企业事实母库>\`，证书号/合同额/人员证号高敏感）、快照走 `tools/select_facts.py` 确定性拷贝（--ids/--sections/--all；逐字拷贝；is_decisive 注入 false＋双复核位头注释；evidence_ref 不带；已存在拒绝覆盖、--force 先备份）。母库条目=节字段＋公共 source/updated_at/owner，**禁录 is_decisive/evidence_ref**（机检 L5）；机检 `tests/check_facts_library.py`（L1–L8 空库绿；负例 12 项错误自证）；永久回归 `tests/test_stage6_regression.py` 14 项。**②③④ 契约与技能版本零变更**（链只读项目快照）；母库不进 git/lock/镜像。「材料归集」技能仍不建（首次拍板不变；遇扫描件归档需求走一次性代劳）。**条目内容未填充**——首填充期与素材库同步，录入流=agent 起草→用户逐项确认→落库（不 OCR）。
- **素材母库结构已交付（repo/v1.7.32，2026-10-21，勿重做）**：`knowledge/` 5 类别目录（同类工程经验/专项工艺/保证措施/服务承诺/技术路线）＋入库规范 README＋tags 受控词表 v1（四维 29 唯一标签）＋条目模板＋`tests/check_knowledge.py`（K1–K9，空库绿；负例探针 7 类全命中后已删）。**阶段 6 重定义**（计划书 v0.20，用户拍板"仅建结构、内容随时补充、通用性优先"）：结构领域中立、新能源降级为 tags 业态维度之一。母库附加三字段（source/updated_at/owner）走 README 约定层，③ 契约零变更、③ 永不直读母库（只读项目 02b 快照）。**条目内容未填充**——首填充期从最近一次中标标书逆向拆条起步，入库红线见 `knowledge/README.md` §六（可核查事实不留正文）。
- **专家复核批次 1–4 修复已交付（repo/v1.7.31，2026-10-21，勿重做）**：两份专家审核报告（《复核结论_20261021》＋《审核报告_…成果逻辑与遗漏复审》）实锤按批次全修——批次 1 代码（C1 同值异形死条件/C4 关键日期槽/C5 qual_timing 三元组契约＋④ gate 联动阻断/C6 draft 章警告/C8 check_business --mode B 金额等值/C12 缺章阻断/D3 style_source 写回/D4 valid_to 警告/F1 标题剥离/F2 EV 收敛/F4 页码四档/F5 白名单警告/F7 PDF 文本层扫描/F8 verify·scrub 上 gate/F12 lock 自检/F14 空格方向/F16b 基线单源载 yaml）；批次 2 断言（s2 T2-11 ×9→73 项、s3 T3-12 ×12＋T3-11f→74 项）；批次 3+4 文档（F10 去空格 4 处/F11 档位声明/F15·F16 计划书目录树/F17 scan_doc docstring/③ 入口「五步」/④ 契约表 03=0.2）。② 0.5.1／③ 0.3.1／④ 0.2.2；计划书升 **v0.19**（现 v0.20）；三技能已重新镜像。
- **②-B 暗标终检已机检化（repo/v1.7.36，2026-10-26，勿重做）**：`check_compliance.py --mode B` 在 `bid_mode=blind` 时按 `01c.typography.identity_ban` 逐串扫 `05_chapters/*.md`，命中计 rc=1 并给出「文件名·行号」（T4-9 四项固化）。**边界**：位图型扫描件无文本层扫不到，页眉页脚水印亦需人工抽检；E 雷同自查仍为人工项（有意不为机检）。
- **⓪ 兜底版本常量须随技能版本同步 bump（易漏）**：`emit_facts.py` 的 `FALLBACK_SKILL_VERSION` 曾落后两个 patch（1.5.0 vs 技能 1.5.1），会在 SKILL.md 版本不可解析的回退路径写入过期版本号并被 ① 的 semver 比对误判为 minor 差异告警；2026-10-26 已修正并 bump ⓪ 至 1.5.2。
- **计划书版本号属易漂移项**：`docs/投标文件Skill建设计划_v0.21.md` 的 §5 目录树、§6.2 `skill_versions` 示例、附录 C 版本钉死三处为「当前状态」描述，技能每次 bump 后须同步刷新（否则 `scan_doc` D4 报错）；而 §0.0 等处为历史叙事，保留原文并追加复核注即可，勿抹掉历史。
- **阶段 2 第二步已交付（repo/v1.7.25，2026-10-21）**：② `bid-compliance-check` 0.3.3→v0.4.0 成稿响应检查实装（`check_compliance.py --mode B`：A-lite 三态/B 偏离表逐行〔人工落点 08_business/deviation-table.md，首列条目id 对行〕/F 复述/退出码 0/1/2；`check_consistency.py` v0.4.0：位置粒度＋工期/金额同语义多值 ⚠️＋同值异形不误报）。验收 #5/#7 欠账补齐。测试：T2-9/T2-10 增 28 项、R3-1 断言升 v0.4.0 口径、示例市真基探针 15/15。**勿重做**。**阶段 2 余项**＝G5 成稿终检中 E 雷同自查（仍人工＋清单）与暗标终检机检化（随阶段 4+）；阶段 2 收口。
- **专家审核意见已处置（repo/v1.7.29，2026-10-21，勿重做）**：《复核意见_v0.16质量分析》＋《进展核验_20261021》五项拍板（A/B1/C1/D/E）落地——s4 汇总文案 T4-7；④ 补齐两个 references（样式与编号规范/雷同与元数据清理）升 v0.2.1；计划书升 **v0.17**（文件已改名 `_v0.17.md`，§11 新增 11.4 阶段 2/11.5 阶段 4 验收小节，C10 glob 自动适配）；旧 10-19 报告头部时效声明；`jsonschema` 4.26.0 已装（validate_plan/emit_facts 走完整校验）。④ 已随 v0.2.1 重新镜像。
- **阶段 5 已交付（repo/v1.7.30，2026-10-21，勿重做）**：①②③ 三份 `SKILL.lite.md`（L0 纯对话版轻量提示词，计划书 §9）——① 0.22.0／② 0.5.0／③ 0.3.0（脚本零变化）；lite 无 frontmatter（防平台误加载路由冲突）、不进 lock（版本随主技能）、IRONLAWS 与主文件逐字一致（C13 机检）；`validate_contract` 新增 **C13**；新增 s5 回归 28 项＋D3 实测卡（`evals/trigger-tests/D3-L0轻量版平台实测卡.md`，5 场景待用户执行）；计划书升 **v0.18**（改名 `_v0.18.md`，§0.0 登记＋§5 目录树三行＋§9 交付登记句＋§11.6 阶段 5 验收小节）。①②③ 已随本次版本重新镜像。
- **阶段 4 主体已交付（repo/v1.7.28，2026-10-21）**：端到端串联＋`evals/`＋盲审工单。① `tests/run_acceptance.py`＝E2E 驱动器（verify 只读核查／--run 临时副本串联，真基只读；--json 报告含 rc；frontier 六态文案冻结）；② `tests/test_stage4_regression.py` 44 项（T4-1 全链 25〔⓪→① G2/G1→②-A G3→③ 42 章 G4→route→writing→②-B 偏离表 1266 行→G5→④ 七脚本 exported→终态 verify PASS〕＋T4-3 跳步负例＋T4-4 状态-产物不一致＋T4-5 frontier 六态＋T4-6 --json＋T4-7 暗标标识扫描〔verify 模式 blind 扫 05_chapters 命中即 FAIL；run 模式 ④ 段向 verify_docx 传 --identity〕）；③ `evals/`（README 记录纪律＋七维记分卡／records 首条示例市真基 machine-chain 至 G3〔⚠️ SELF-ONLY〕／trigger-tests D1/D2 用户实测卡／cross-audit 套件设计级盲审工单）。示例市真基 verify PASS＋--run 至 G3 无副作用。**勿重做**。**余项**＝D1/D2 用户实测回填、盲审工单投递与合并（回填前最高 ⚠️ SELF-ONLY）、真实项目 ③ 写作段试跑。
- **阶段 3 已交付（repo/v1.7.27，2026-10-21）**：④ `bid-docx-export` 0.1.1→v0.2.0 导出链实装——`scripts/` 九件（`_common`/`pdfutil`/`build_style_profile`〔三档样式档〕/`index_evidence`/`check_evidence`〔五项〕/`assemble_pdf`〔纯标准库 PDF writer＋对象级合并〕/`export_docx`/`scrub_metadata`〔普通/暗标两套，修订记录不自动接受〕/`verify_docx`〔回读校验过才写 exported〕）＋`references/证明材料装配规则.md`。纯标准库零三方依赖。测试：`test_stage3_regression.py` 59 项（T3-1~T3-11），已镜像运行目录（备份 %TEMP%\skills_bak_t3_20261021_145551）。**勿重做**。实施期修二缺陷：闸门失败 `failed_nodes` 落盘；`scrub_metadata` 修订记录 rc=1 被 `rc=0` 覆盖。
- **阶段 1 已关闭（repo/v1.7.23，2026-10-19）**：A 系列 01b 全量（1266 条／第五章 9 节）、B 系列 ⓪ 产物漂移与 #0/#2 复验、C 系列 §11.2 十一条重跑＋两轨对账（01 由 53 重建为 67，Markdown＝JSON 逐类一致）全部完成；① v0.21.0。**勿重做**。**未完**＝阶段 4（端到端/evals/双模型）、阶段 5/6；D1/D2 真实平台触发与拒绝实测仍待用户；`03c` n-1131 短名保留；`jsonschema` 未装时 `01` 仅结构子集校验。
- 2026-10-19 已将五技能镜像至 `~/.config/opencode/skills/`（① 0.21.0，镜像前备份在临时目录）；2026-10-21 ③ 镜像已随 v0.2.0 更新（robocopy 排除 `__pycache__`）。此后技能改动需重新同步运行目录，否则平台仍用旧版。
- `workdir/acceptance/` 内的 probe_*.py 是一次性探针，不是回归套件；永久回归只有 `tests/` 的十个入口脚本（validate＋s1~s6＋check_knowledge＋check_facts_library＋scan_doc 归档文档另算）。

## Git（2026-10-19 核实）

- 仓库 = GitHub 克隆 `https://github.com/chenyongle123/skills-toolkit.git`（main 分支，提交人 Chen Yongle，经 GitHub Desktop 同步）。
- **终端/沙箱直接敲 `git` 不可用**：PATH 中 `C:\Program Files\Git\{bin,cmd}` 为失效残留（目录不存在，本机无独立 Git for Windows）。实际 git 2.53.0 由 **GitHub Desktop 内嵌**提供：`$env:LOCALAPPDATA\GitHubDesktop\app-*\resources\app\git\cmd\git.exe`（app-* 版本号会变，通配取最新）。
- 截至 2026-10-19：已提交且已推送 = 至 `038d0d0`（⓪ v1.5.1，含 tag）；**repo/v1.7.4–v1.7.23 全部施工成果未提交**（A/B/C 系列：CHANGELOG/README/lock/①② SKILL+schema/脚本/测试/文档）＋未跟踪 `.opcteam/`、`AGENTS.md`、`docs/` 收口与验收文档。
- 已知缺口（**用户已拍板不处理，2026-10-19，勿再主动提议**）：⓪ v1.5.1 已 commit＋tag＋lock 刷新但 CHANGELOG 无对应条目；`.gitignore` 未含 `.opcteam/`；v1.7.4–v1.7.23 未提交成果保持现状（何时提交由用户经 GitHub Desktop 自行决定）。

## 结构速览

- `skills/tender-document-review`（⓪，v1.5.1）→ `bid-response-plan`（①，v0.22.0 含 SKILL.lite.md L0 版）→ `bid-compliance-check`（②，v0.5.1 成稿响应版＋lite：②-A 覆盖检查＋②-B `--mode B` 成稿响应检查＋check_consistency〔日期槽/同值异形 v0.5.1 修〕＋check_business --mode B 行内金额核对）→ `bid-technical-proposal`（③，v0.3.1 正文能力版＋lite）→ `bid-docx-export`（④，v0.2.2 导出链实装：三档样式档〔基线单源载 yaml〕→证据索引→五项检查→PDF 装配〔EV 收敛/页码四档〕→docx 生成→元数据清理→回读校验；入口 gate＝expired 联动阻断/缺章/draft 章/style_source/lock 自检）：串行链，靠产物契约＋"入口校验/出口指路"衔接，无编排技能。①②③ 另有 `SKILL.lite.md`（L0 纯对话平台粘贴用，无 frontmatter、不进 lock、C13 机检）。
- `delivery-audit`／`business-contract-review`／`quantity-takeoff-building` 为套件外技能，**不进 lock**（lock 的 `_scope.out_of_scope` 字段已声明此边界）。
- **`quantity-takeoff-building` v0.1.0（repo/v1.7.26，2026-10-21）**：房建工程量计算执行层，`skills/quantity-takeoff-building/`，19 文件 + README；自带 `tests/run_tests.py`（35 断言，独立于本仓库 `tests/` 四入口）。**实测覆盖仅混凝土／钢筋／依附几何模板**；机电安装**覆盖为零**（设计见 `docs/quantity-takeoff-机电计量设计计划书.md`）；砌体/钢结构/桩基/门窗/屋面/防水/保温/楼地面为"待核实"骨架不可用。`SKILL.md` 的"通用房建"为**已知超额声明**，待用户裁定后修正。**待决阻塞项**：机电主路线（A 模型驱动／B 双图对读／C 规则推定）、预留量口径、规则原文来源——未定前勿写新代码。
- `knowledge/` = **素材母库（M2b）**：仓库级资产（不进 lock、不镜像运行目录——③ 只读项目 02b 快照、永不直读母库）。结构已落成（repo/v1.7.32）：5 类别目录＋入库规范＋tags 词表＋条目模板＋K1–K9 机检；条目内容按业态持续补充。
- **企业事实母库（M2）**：**仓库外本地目录** `<企业事实母库>\`（敏感数据永不入 git；repo/v1.7.33 建库）＋仓库侧工具 `tools/select_facts.py`（母库→项目 02_facts.yaml 快照）＋`tests/check_facts_library.py`（L1–L8 机检）＋`tests/test_stage6_regression.py`（14 项）。两级库语义与素材母库同构：②③④ 只读项目快照，永不直读母库。
- 当前施工前沿：**企业事实母库＋快照链已交付（repo/v1.7.33，2026-10-21：母库结构落位 `<企业事实母库>\`〔README 红线/模板/五节空 yaml〕＋`tests/check_facts_library.py` L1–L8〔空库绿，负例 12 项自证〕＋`tools/select_facts.py` 确定性快照〔覆盖保护/--force 备份/选择集空报错〕＋s6 回归 14 项；计划书 v0.21〔§0.0 登记/§5 目录树 tools/ 行/§6.3 两级事实库表/§11.8 验收/R2 注记/新增 R20〕；门禁十一件全绿）**。上一前沿：素材母库结构（repo/v1.7.32）、专家复核批次 1–4（repo/v1.7.31）、阶段 5（repo/v1.7.30）。**待用户**：D1/D2/D3 三张实测卡（evals/trigger-tests/）、盲审工单投递（回填前 ⚠️ SELF-ONLY）、真实项目 ③ 写作段试跑。下一步＝素材/事实双母库首填充期（最近一次中标标书逆向拆条＋企业证书/合同清单逐条确认录库）。
