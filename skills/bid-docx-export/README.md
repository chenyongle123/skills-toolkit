# bid-docx-export（④ 投标文件排版导出）

套件第 ④ 环，链路收口：**只改外观与装订，一个字的内容都不改**；未过 G5 拒绝导出。

## 输入

| 输入 | 说明 |
|---|---|
| `stage = recheck_confirmed` | 入口 stage |
| `05_chapters/*.md` | 正文定稿 |
| `01c_format-outline.json` | 章名（逐字）与排版参数 |
| `06_compliance/` | `form-check.md` 必须无空项；`consistency-issues.md` 缺失记警告 |
| `evidence/` | 证明材料扫描件（PDF 一等公民，图片按 1 页计） |

**G5 闸门**：`form-check.md` 有空项 → 阻断；②-A 结论中未解决的 `expired` → 阻断导出（④ 不重判时效，仅联动结论）；`style_source` 不一致 → `failed_nodes` 落盘并阻断；闸门失败零产物。

## 产出

`03b_evidence-index.json`；`06_compliance/evidence-check.md`；`07_out/{style-profile.yaml, 排版依据说明.md, 投标文件_含附件.pdf, pagination.json, 投标文件.docx, verify-report.md}`；通过回读校验后 `stage = exported`。

## 导出链（七脚本按序，统一 `--bid`）

| 序 | 脚本 | rc |
|---|---|---|
| 1 | `build_style_profile.py`（甲方模板档加 `--template`） | 0/2 |
| 2 | `index_evidence.py` | 0/2 |
| 3 | `check_evidence.py`（可加 `--max-mb N`） | 0/1/2 |
| 4 | `assemble_pdf.py` | 0/1/2 |
| 5 | `export_docx.py` | 0/1/2 |
| 6 | `scrub_metadata.py`（`--mode normal|blind`，暗标加 `--identity`） | 0/1/2 |
| 7 | `verify_docx.py`（通过才写 `exported`） | 0/1/2 |

rc：0 成功；1 须处置（错误项/残留/超限）；2 前置缺失或闸门阻断。纯标准库零三方依赖，Python ≥ 3.8。

插图与残留反查参数：`export_docx.py --docx-max-mb 50 --img-max-mb 5`（成品超限 rc=1，单张超限仅告警）；
`verify_docx.py --whitelist "业绩项目名,人员名" [--residual-strict]`（白名单反查，默认信息态）。

## 排版三档（不得颠倒）

① 招标明示（`01c.typography` 逐项照录，v0.25.0 起由 ① 自 ⓪ `blind_format` 派生；**关键项〔字体/字号/行距/页边距/页码〕空值或不可解析＝执行阻断 rc=2，不静默代基线**——招标档缺陷＝上游 ① 抽取层缺口；套件扩展项 indent 及 `page_limit` null 回落合法）→ ② 甲方模板（纯标准库解析 docDefaults/sectPr）→ ③ 通用中文基线（**仿宋、正文小四、1.5 倍行距、首行缩进 2 字符**）。选档结果写入《排版依据说明.md》。暗标叠加层与 `bid_mode=blind` 绑定（`overlay_blind`）。

## 版本

`0.2.6`（**残留反查白名单比对修复**：本项目名带「项目/工程」后缀时会被误报为旧项目残留（真实项目名几乎都带后缀，等于必误报）；改为剥前导虚词＋两端各剥一个末尾通名后再包含比对，由 `tests/test_stage8_regression.py` T8-3 锁死）
`0.2.5`（**插图管线实装**：`![题注](assets/x.png)` → 校验源文件存在〔缺失记 failed_nodes＋【待补图】占位〕→ 嵌入 `word/media/`＋OpenXML drawing，暗标剥离 JPEG EXIF；新增 `--docx-max-mb`/`--img-max-mb`。**不做像素级压缩**。另 `verify_docx.py` 新增旧项目残留白名单反查 `--whitelist`/`--residual-strict`）+ `0.2.4`（用户口径：排版档来源）
`0.2.3`（fail-loud 修复：招标档关键项〔字体/字号/行距/页边距/页码〕空值或不可解析＝执行阻断 rc=2 不再静默代基线〔D4〕；`parse_size` 同长度键碰撞修复；`page_limit` 无数字→告警＋铁律 3 提示；`parse_style_yaml` 支持块序列/`[]` 空列表）；`0.2.2`（专家复核批次 1–4 修复：入口闸门强化〔expired 联动阻断/缺章/draft 章/style_source〕、页码四档实装、`[[EV:]]` 替换收敛、暗标 PDF 文本层扫描、中英文空格方向对齐、基线单源载入 yaml、附件引用去空格口径）；`0.2.1`（references 补全：`样式与编号规范.md`＋`雷同与元数据清理.md`，计划书 §5 目录树闭合，行为无变化。阶段 3 实装版：导出链七脚本全落地——三档样式档/证据索引/五项证据检查/PDF 装配/docx 生成/元数据清理/回读校验；雷同自查机检按计划书修订取消转人工。0.1.1 为骨架版）

## 操作须知

> **天坑**（计划 §8.8.3）：AI 生成或下载的文档，务必「另存为」后再编辑，不要直接打开就改——某次保存异常或格式冲突可能毁掉整篇内容。

| # | 要求 | 原因 |
|---|---|---|
| 1 | 每次导出另存新文件名（带时间戳），不覆盖上一版 | 排版比对、回退需要 |
| 2 | 导出后先看页数与目录，再看内容 | 页数超限/目录错位是电子标最高频退回原因 |
| 3 | 人工改过的 docx 不得再交给 ④ 重跑覆盖 | 会冲掉人工修改；要改先改 md 再重导 |
| 4 | 交付前确认修订记录已接受、批注已删除 | 残留修订会暴露修改过程（§8.6.3） |

## 已知限制

| # | 限制 | 说明与处置 |
|---|---|---|
| 1 | **docx 成品不含自动目录** | `export_docx.py` 不生成 `fldChar TOC` 域，且全包**不调用** LibreOffice（`soffice`）/ Word COM，不会触发"更新域"。PDF 侧目录页码由自研两遍法收敛（含页数自洽 rc=1 自证）✅，**目录以 PDF 成品为准**；docx 如需目录，须人工在 Word 中「引用 → 目录」插入并更新域。 |
| 2 | **插图不做像素级压缩** | 插图管线做存在性校验／显示尺寸收敛／嵌入／成品体积机检／暗标剥离 JPEG EXIF，**但不重编码压缩**（套件坚持纯标准库零三方依赖）。单张超 `--img-max-mb`（默认 5MB）只告警不阻断，**须人工压缩后重导**；PNG 的 tEXt 元数据不清理，暗标项目须人工确认。 |
| 3 | **旧项目残留反查依赖白名单** | 白名单由 `00_metadata.project` 三字段＋`--whitelist` 构成；**未填 project 且未给 `--whitelist` 时不执行本项并明确提示"不得视为已查"**。本单位既有业绩项目名、人员名须人工补充进白名单，否则会被当作"白名单外"报出。 |

## 依赖

`references/流水线交接约定.md`、`references/常见错误.md`、`assets/*.schema.*`。
