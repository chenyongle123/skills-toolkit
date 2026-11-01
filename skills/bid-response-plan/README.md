# bid-response-plan（① 投标响应策划）

投标文件编写套件的第 ① 环，也是**全流程入口**：用户说"帮我做这个标"时命中本技能，本技能负责判断前置产物是否齐备并指路，而不是自己去解析招标文件。

## 输入

| 输入 | 必填 | 来源 |
|---|---|---|
| `00_metadata.json` | 是 | ⓪ 创建（`stage=reviewed`） |
| `01_tender-facts.json` | 是 | ⓪ 产出 |
| `02_facts.md` / `02_facts.yaml` | 是（可缺但会显著告警） | 知识库维护人 |

## 产出

| 产物 | 阶段 |
|---|---|
| `01b_spec-items.json` 技术规范条目 | 1 |
| `01c_format-outline.json` 格式章标题＋排版要求 | 1 |
| `03_bid-plan.json` 任务卡（唯一真源） | 1 |
| `04_outline.json` 章节树 | 1 |
| `03c_business-forms.json` 商务表框架（不含金额） | 1 |
| `素材缺口清单.md` 待澄清/待补录事项 | 1 |

## 关卡

- **G2（入口）**：人工确认事实库完整准确；通过后写 `facts_confirmed`。
- **G1（出口）**：人工确认目录骨架章名/顺序与篇幅分配；通过后写 `plan_confirmed`。

## 版本

- 技能：`0.29.0`（**全局投标承诺锁**：新增产物 `03d_commit-lock.json`〔数字锁／技术路线锁／命名实体锁〕，G2 由单确认扩为「事实库＋承诺锁」双确认；③ 步 1 前置注入照抄，②-B `check_commit_lock.py` 做「锁→稿」校验）
- 技能：`0.26.0`（锚定同义回退：`resolve_chapter_id` 章节锚定「价格」↔「报价」标题词同义互备，格式章异写不再误阻断）；此前 `0.25.0`（排版要求自动派生：`01c.typography` 自 ⓪ `01.blind_format` 逐项派生，D4 根修复——旧版发空串常量致 ④ 招标档静默回落基线）、`0.24.0`（任务卡真值派生重构，废弃 48 张硬编码模板）、`0.23.0`（入口闸门 `gate()` 零产物阻断）、`0.22.0`（阶段 5：`SKILL.lite.md` L0 轻量版）、`0.2.0`（阶段 1 功能版：任务卡/目录骨架/`01b`/`01c`/`03c` 生成 + 素材缺口清单 + `preconditions`）
- 读取契约：`01` 的 `contract_schema_version = "0.4"`

## 依赖

`references/流水线交接约定.md`（四份逐字一致）、`references/常见错误.md`（8 条铁律反例）、`assets/*.schema.json`。
轻量版：`SKILL.lite.md`（L0 纯对话平台粘贴用；无 frontmatter，不进 `skills-lock.json`）。

## 已知限制

- **章节树派生优先，常量仅兜底**：`01c_format-outline.json` 的章节树由 `build_bid_plan.py` 自动发现 bid 根 `_headings_*.json`（⓪ 对招标格式章的标题抽取件，字段 page/number/title/level，level 必填最浅=1）——恰一份即派生真实章节树；零份才走 `scripts/parse_format_outline.py` 内固化的 `FORMAT_CHAPTERS` 常量并打显著警告（该常量取自「示例发包人示例市100MW风电项目 EPC」招标文件「投标文件格式」章逐字结构，绑定示例项目）；多份或契约损坏直接 rc2。纯平铺树（无组头）、锚定槽空、商务表章题两跳不中均 fail-loud。*换新项目必须重新抽取该招标文件的「投标文件格式」章并覆盖 `FORMAT_CHAPTERS` 常量（脚本头部注释与 SKILL.md 均有同注）**，否则目录骨架会张冠李戴。排版要求（`typography`）不受此限——v0.25.0 起自 ⓪ `01.blind_format` 自动派生。
- **01b 条目同样绑定本项目，且数据源不入库**：`01b_spec-items.json` 为本项目「技术标准和要求」章全量逐行抄录（1266 条），数据源为 `assets/01b-spec-items.json`——**该数据文件已 gitignore、仅本机留存**（含招标原文逐条抄录，属 AGENTS.md:54 红线，不进公开仓库）。换新项目须按 `references/技术规范条目抽取规则.md` 同口径重新抄录后放入该路径；**文件缺失时 `parse_spec_items.py` 产出 `items=[]` 并显著告警**，不猜、不兜底示例值（2026-11-01 起，见 CHANGELOG `repo/v1.7.52`）。
- 可选依赖 `jsonschema`（安装了才对 `03_bid-plan.json` 做完整 schema 校验，未安装输出 `WARN` 并只做结构自检）。
