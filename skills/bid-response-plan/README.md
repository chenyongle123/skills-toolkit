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

- 技能：`0.2.0`（阶段 1 功能版：任务卡/目录骨架/`01b`/`01c`/`03c` 生成 + 素材缺口清单 + `preconditions` 补遗对照前置项；入口校验、状态读写、8 铁律保持）
- 读取契约：`01` 的 `contract_schema_version = "0.4"`

## 依赖

`references/流水线交接约定.md`（四份逐字一致）、`references/常见错误.md`（8 条铁律反例）、`assets/*.schema.json`。

## 已知限制

- **章节树绑定本项目**：`01c_format-outline.json` 的章节树由生成脚本 `scripts/build_bid_plan.py` 内固化的 `FORMAT_CHAPTERS` 常量产出，该常量取自「中能建深州100MW风电项目 EPC」招标文件第七章逐字结构。**换新项目必须重新抽取该招标文件的「投标文件格式」章并覆盖 `FORMAT_CHAPTERS` 常量（脚本头部注释与 SKILL.md 均有同注）**，否则目录骨架会张冠李戴。
- `01b_spec-items.json` 当前仅含代表项 2 条，「技术标准和要求」全量抽取待补。
- 可选依赖 `jsonschema`（安装了才对 `03_bid-plan.json` 做完整 schema 校验，未安装输出 `WARN` 并只做结构自检）。
