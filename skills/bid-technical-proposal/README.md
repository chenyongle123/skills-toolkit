# bid-technical-proposal（③ 投标技术标正文）

套件第 ③ 环：**一次只写一章、一章一次确认**。技术路线未经人确认（G4），不动笔。

## 输入

| 输入 | 说明 |
|---|---|
| `stage = check_confirmed` | 入口 stage |
| `01` / `01b` / `01c` | 招标事实与格式要求（只读） |
| `03_bid-plan.json` / `04_outline.json` | 任务卡与章节树 |
| `02_facts` | 可核查事实（逐字引用，不改写） |
| `02b_knowledge/` | 本次项目素材**快照**（可改写、可组合） |

**不直读跨项目母库**：母库持续增删，直读会导致同一项目两次生成结果不一致。

## 产出

`05_chapters/<chapter_id>.md`（可加中文后缀）：frontmatter 过 `assets/chapter.schema.json`（章节定位＋G4 状态）；正文每段标注 `[[F:facts-id]]` 或 `[[S:评分点-id]]`，无来源段落不得进入交付稿。插图源文件置 `05_chapters/assets/`。

## 五步循环

读任务卡 → 取素材与事实 → **G4 确认技术路线** → 按章撰写并标注来源 → 背对背复核。操作细则见 `references/章节写作五步循环.md`。

## 脚本（零三方依赖）

| 脚本 | 用途 | 退出码 |
|---|---|---|
| `scripts/check_facts.py --bid <bid> [--chapter n-xxxx]` | 事实/评分点引用存在性、无来源段落、缺 source（R1）、超 12 个月提示（R2） | 0 过／1 有错误／2 输入缺失 |
| `scripts/word_count.py --bid <bid>` | 各章字数对照 `04_outline.word_target`（MISSING／⚠超偏差标记） | 0 出表／2 无 outline |

## 版本

`0.3.1`（专家复核批次 3–4：入口校验计数修正「五步」、去「骨架版」陈旧措辞、`word_count.py` MISSING/孤儿 rc=1）；`0.3.0`（阶段 5：新增 `SKILL.lite.md` L0 纯对话版轻量提示词——五步循环单章成文每步【能力依赖：L2】+降级指令、铁律自包含、R7 状态快照、强制"一章一轮"；一致性由 `validate_contract` C13 机检；脚本零变化）；`0.2.0`（阶段 2 正文能力版：五步循环、素材路由、事实核验、写作规范／图表题注／暗标／结构参考四份细则、`chapter.schema.json` 产物契约与上述两脚本交付；0.1.x 历史＝入口校验＋状态读写）

## 依赖

`references/流水线交接约定.md`、`references/常见错误.md`、`assets/*.schema.*`。
轻量版：`SKILL.lite.md`（L0 纯对话平台粘贴用；无 frontmatter，不进 `skills-lock.json`）。

> 跨章一致性检查**不在本技能实现**——归属 ②-B 的 `check_consistency.py`（全套件唯一实现，现为骨架版），成稿后由 ②-B 调用。
