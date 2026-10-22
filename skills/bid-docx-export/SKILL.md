---
name: bid-docx-export
version: 0.2.2
description: 投标材料排版与导出。按招标要求的排版参数生成样式档并导出 Word/docx，装配证明材料扫描件为合订 PDF，清理文档元数据并做雷同自查回扫，输出排版依据说明。当用户说"导出 Word""排版""按招标格式调版式""把成稿装订成 PDF""清掉文档属性""页数超限检查"时使用。**须已有成稿**；用户问"投标文件格式章有什么要求""格式怎么规定的"属招标文件解读（tender-document-review），本技能不做解读。本技能不改内容、不判定合规；未过成稿终检（G5）拒绝导出。
---

# 投标文件排版导出（套件第 ④ 环）

> **技能版本：v0.2.2（2026-10-21；专家复核批次 1–4 修复）：入口闸门强化（②-A `f_qual_timing` expired 联动**阻断**〔读新契约 dict/list 双形态，解析失败即阻断〕＋缺章〔01c 节点 vs 05_chapters〕＋`status≠final` 章＋`style_source` 缺失 warn/不一致 fail＋F12 skills-lock 运行时自检 warn）；F4 页码四档实装（none/header_center/footer_center/footer_outer，docx 部件动态组装）；F2 `[[EV:]]` 替换收敛循环（≤3 轮，pagination 记 `ev_converged`）；F7 暗标 PDF 文本层扫描（`_common.pdf_identity_hits`，verify/scrub 共用）；F1 标题剥离 docx/PDF 口径统一；F14 中英文空格检查反转对齐计划书 §8.7 规则 2（扫误加空格，信息态）；F5 字体白名单外照录＋警告；D3 `style_source` 写回闭环；D4 证据 `valid_to` 空值警告；F16b 基线单源（`BASELINE` 载自 `通用中文基线.yaml`，缺失即阻断）；F10 附件引用去空格口径「见附件A-xx」。v0.2.1：补齐 `references/样式与编号规范.md` 与 `references/雷同与元数据清理.md`。v0.2.0（阶段 3 实装版）：完整导出链七脚本落地——三档样式档→证据索引→五项证据检查→合订 PDF 装配→docx 生成→元数据清理→回读校验（通过才写 exported）；雷同自查机检按计划书修订取消（转人工＋清单）。v0.1.1（2026-10-17）为骨架版。**
> 受套件总则（8 条铁律）约束；流水线状态机见 `references/流水线交接约定.md`。

## 一、定位与边界

**一句话**：只改外观与装订，**一个字的内容都不改**；未过 G5 一律拒绝导出。

| 做 | 不做 |
|---|---|
| 按招标排版要求生成样式档并套用 | 改章节名、改正文、补写段落 |
| 扫描件索引 → 装订顺序 → 合订 PDF | 从扫描件 OCR 取事实填表 |
| 元数据清理（作者/最后修改人/公司/模板路径/修订记录） | 判定资质是否过期（②-A 负责，④ 只联动其结论） |
| 回读校验（页数、页码、中英文空格、元数据残留） | 生成报价、填商务表金额 |

**排版三档优先级**（不得颠倒）：① 招标明示（`01c.typography`）→ ② 甲方模板（`client_template`）→ ③ 通用中文基线（**仿宋、正文小四、1.5 倍行距、首行缩进 2 字符**）。选档结果写入 `排版依据说明.md`，无招标要求时须写明"无招标要求，采用基线"。

## 二、入口校验（闸门：`_common.gate`，步 4/5 共用；失败零产物）

1. `00_metadata.json` 存在；`stage` 必须为 **`recheck_confirmed`**（未过成稿终检 G5 拒绝导出）。
2. 前置产物：`05_chapters/*.md` 有章节文件、`01c_format-outline.json` 在、`06_compliance/form-check.md` 在且**无空项**（值域 `—`/`-`/`无`/空白即算空项）。
3. `06_compliance/consistency-issues.md` 缺失 → 信息态警告（②-B 产物，旧管线放行但提示）。
4. ②-A 结论中未解决的 `expired` 项 → **阻断导出**（④ 不重判时效，仅联动其结论；`expiring_soon` 不阻断）。
5. `style_source` 与 `01c.typography.source` 必须一致；不一致记入 `failed_nodes` 落盘 `00_metadata.json` 并阻断。
6. 闸门失败时 docx/PDF **一律不生成**（零产物），`failed_nodes` 去重追加落盘。

## 三、导出链（七脚本按序执行，统一 `--bid <bid目录>`）

| 序 | 脚本 | 产出 | rc 语义 |
|---|---|---|---|
| 1 | `scripts/build_style_profile.py` | `07_out/style-profile.yaml`＋`排版依据说明.md` | 0 生成；2 前置缺失 |
| 2 | `scripts/index_evidence.py` | `03b_evidence-index.json` | 0 生成；2 `evidence/` 缺失或空 |
| 3 | `scripts/check_evidence.py` | `06_compliance/evidence-check.md` | 0 无错误项；1 有错误项（装配前须闭环）；2 缺 `03b` |
| 4 | `scripts/assemble_pdf.py` | `07_out/投标文件_含附件.pdf`＋`pagination.json` | 0 生成；1 装配错误/超出页数上限；2 前置缺失/闸门阻断 |
| 5 | `scripts/export_docx.py` | `07_out/投标文件.docx` | 0 生成；1 错误；2 前置缺失/闸门阻断（零产物） |
| 6 | `scripts/scrub_metadata.py` | 清洁 docx＋PDF | 0 清洁；1 须人工处置（修订记录/暗标标识命中）；2 缺 docx |
| 7 | `scripts/verify_docx.py` | `07_out/verify-report.md`＋`stage=exported` | 0 通过；1 残留/不符；2 前置缺失 |

- **步 1 三档**：招标明示（`01c.typography` 逐项，空值回落基线并在 `sources` 逐项记录）→ 甲方模板（`--template <docx>` 必传，纯标准库解析 docDefaults/sectPr）→ 通用中文基线；暗标叠加层与 `bid_mode=blind` 绑定（`overlay_blind`）；档位/基线参数/编号页码口径详见 `references/样式与编号规范.md`。
- **步 2 证据索引**：`evidence/` 下 PDF 按实测页数、图片按 1 页计；附件号 `A-NN`（文件名前缀优先，无前缀按序自动补号）；`fact_ref` 只做文件名↔任务卡关键词匹配，匹配不上留空**不猜**（铁律 1：扫描件不作事实来源）。
- **步 3 五项检查**：缺件（废标级排前）/日期一致性（时效归 ②-A）/页数超限（估算）/文件大小超限/索引自洽；只报事实态（铁律 4）。
- **步 4 装配**：总页数 = 正文（含目录）＋证据，`pagination.json` 自证（PDF 实测复核）；超 `page_limit` → rc=1（铁律 3）。
- **步 5 docx 生成**：章名逐字取 `01c`（铁律 2）；`[[EV:]]`→「见附件A-xx（第N–M页）」（页码来自 pagination；附件号与「（」之间不加空格，与 verify 中英文混排不空格口径一致）；`[[F:]]`/`[[S:]]` 溯源标注剔除；页脚 PAGE 域。
- **步 6 两模式**：`--mode normal|blind`（缺省读 `metadata.bid_mode`）；两种标都清 creator/lastModifiedBy/Company/模板路径/自定义属性/批注；**修订记录（w:ins/w:del）不自动接受**（会改内容），存在即 rc=1；暗标另扫页眉页脚/正文/属性标识串（`--identity "公司名,人名"`），命中报事实态，改内容归 ③；字段级口径与验收对照见 `references/雷同与元数据清理.md`。
- **步 7 回读校验**：章名逐字/占位符残留/元数据残留/页数闭合（PDF 侧真值复核）/暗标标识；中英文空格为信息态。**全过才写 `stage=exported` 并登记 `skill_versions`**；任何残留即 rc=1，不静默放行。

## 四、铁律（八条，与 ①②③ 逐字一致）

<!-- IRONLAWS:BEGIN -->
1. **不编造事实**：业绩、人员、证书、参数、金额、工期，未见于事实库即写 `【待填：××】`；素材库内容可改写，但不得产出任何可核查事实。
   - **扫描件不作事实来源**：营业执照、资质证书、合同扫描件只作证明材料，证书编号、有效期、合同额等一律由知识库维护人录入事实库；**AI 不得从扫描件 OCR 后直接填表**——OCR 错一位数字即构成提供虚假材料。
   - **图文不符时以事实库为准并报警**：发现扫描件与事实库不一致，输出`待核`，不自动择一。
2. **不改章节名与顺序**：章节名一律取自 `01c`，逐字不改；格式废标优先于得分优化。
3. **暗标匿名与页数上限**：暗标项目全文不得出现投标人名称、标识、人员姓名及其他可识别信息；**无论是否暗标，正文 + 证据的总页数均不得超出 `01c.typography.page_limit`**（未载明上限时按招标的隐含要求估算并写明依据）。
4. **不给法律结论**：不判定"是否废标""是否违法"，只报事实态。
5. **不代投标人决策**：投标与否、报价几何、让不让步，不给建议。
6. **不做未授权承诺**：技术参数、工期、售后承诺必须来自事实库或用户明示。
7. **每段可回溯**：无来源的段落不得进入交付稿。
8. **技术路线须有来源** ★：技术路线、实现架构、工艺选择、设备选型必须来自 `02_facts`、`02b_knowledge` 或用户明示。**AI 自行推演出的路线即使看起来合理，也不得进入交付稿**——路线错了不是改几句话能补的，只能重写。无来源时输出 `【待确认：技术路线】`，交 G4 关卡由人定。
<!-- IRONLAWS:END -->

> 反例见 `references/常见错误.md`；尤其注意反例 3（暗标与页数）与反例 1（扫描件不作事实来源）。

## 五、交接

- 按 `references/流水线交接约定.md` 读写状态；①—④ 链路在本技能收口。
- **本技能出口**：写 `stage = exported`，打印：

```
交付完成：07_out/投标文件.docx、投标文件_含附件.pdf、排版依据说明.md
提醒：电子标平台上传前请人工核对页数与文件大小上限；另存后再编辑，勿直接改交付件。
```

- `style_source` 与 `01c.typography.source` 必须一致；不一致记入 `failed_nodes` 并阻断。

## 六、契约版本

| 项 | 值 |
|---|---|
| 读取 | `01c`（`0.2`）、`03_bid-plan`（`0.2`）、`06_compliance/*.md`、`compliance-report.json`（②-A 结论联动） |
| 产出 | `03b_evidence-index.json`（`0.1`）；`07_out/{style-profile.yaml, 排版依据说明.md, 投标文件_含附件.pdf, pagination.json, 投标文件.docx, verify-report.md}`；`06_compliance/evidence-check.md` |
| 自检 | 读 `skills-lock.json`，三级降级，不阻断 |

## 七、本版本能力范围（v0.2.2，批次 1–4 修复＋阶段 3 实装）

| 能力 | 状态 |
|---|---|
| 入口闸门（G5/expired 联动/style_source 一致/failed_nodes 落盘/零产物） | ✅ 已实现 |
| 三档样式档（招标明示/甲方模板纯标准库解析/通用中文基线）＋排版依据说明 | ✅ 已实现 |
| 证据索引（实测页数/附件号/fact_ref 关键词匹配不猜）＋五项证据检查 | ✅ 已实现 |
| 合订 PDF 装配（纯标准库 PDF writer＋对象级合并）＋pagination 自证与 PDF 实测复核 | ✅ 已实现 |
| docx 生成（章名逐字取 01c、[[EV:]]→页码引用、[[F:]]/[[S:]] 剔除、PAGE 域） | ✅ 已实现 |
| 元数据清理（普通标/暗标两套；修订记录不自动接受；PDF /Info 清空） | ✅ 已实现 |
| 回读校验（章名/占位符/元数据/页数闭合/暗标标识）＋`exported` 状态与版本登记 | ✅ 已实现 |
| 雷同自查机检 | ➖ 已按计划书修订取消（转人工＋清单，G5 环节人工执行；导出侧口径见 `references/雷同与元数据清理.md`） |

> 运行环境：Python ≥ 3.8，纯标准库零三方依赖（PDF/docx 均自研生成，不依赖 python-docx/reportlab/pypdf）。
