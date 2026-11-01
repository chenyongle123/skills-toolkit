# 审核报告：投标文件 Skill 建设计划 v0.16 成果逻辑与遗漏复审

> 审阅时间：2026-10-21
> 审阅对象：⓪ tender-document-review v1.5.1、① bid-response-plan v0.21.0、② bid-compliance-check v0.4.0、③ bid-technical-proposal v0.2.0、④ bid-docx-export（skills-lock 记 0.2.0 / SKILL.md 实读 0.2.1）
> 审阅基准：docs/投标文件Skill建设计划_v0.17.md（下称"计划书"；v0.16 冻结基线已并入 v0.17，本报告章节号均以 v0.17 为准，详见 F18）
> 审阅方式：直接读取源码、交付物与测试脚本核对逻辑，**不看日志**；所有缺陷均经源码定位或最小复现/实测运行确认

**结论速览**：确认缺陷与问题 20 项（F1–F19 + F16b），其中**逻辑错误 8 项**、**引用断链与清单不闭合 6 项**、**与 SKILL/计划书声明不一致 4 项**、**内容性遗漏与维护风险 2 项**；另实测确认正面结论 11 项。按修复紧迫度给出 P0/P1/P2 建议。

---

# 一、问题总览表

| 编号 | 分类 | 对象 | 一句话 | 优先级 |
|---|---|---|---|---|
| F1 | 逻辑错误 | ④ export/assemble | 标题前缀剥离普遍少剥 1 字符，docx/PDF 两版标题带前导空格 | P1 |
| F2 | 逻辑错误 | ④ assemble_pdf.py | PDF 装配未调用 replace_ev，正文残留 `[[EV:ev-xxx]]` 字面量 | P0 |
| F3 | 逻辑错误 | ④ verify_docx.py | 章名/章号校验为子串查找，无法证明标题逐字一致 | P2 |
| F4 | 逻辑错误 | ④ export_docx.py | page_number 档位不兑现，恒写页脚居中 PAGE 域（9pt 硬编码） | P0 |
| F5 | 逻辑错误 | ④ build_style_profile.py | parse_font 返回值被丢弃（恒等三元），字体白名单形同虚设 | P1 |
| F6 | 逻辑错误 | ④ build_style_profile.py | margins 正则紧邻匹配，"2.54cm" 隔断致回落基线 | P2 |
| F7 | 逻辑错误 | ④ verify_docx.py | 暗标标识仅扫 docx，不扫装配后 PDF 文本层 | P1 |
| F8 | 声明不一致 | ④ verify/scrub | 出口校验器与元数据清理器未调用 gate()，出口未上闸门 | P1 |
| F9 | 遗漏/潜伏 | ④ dump_yaml | YAML 空列表读回为字符串 "[]"，下游当前未消费 | P2 |
| F10 | 声明不一致 | ④ replace_ev | 输出「见附件A-01」无空格，与 SKILL 声明「见附件 A-xx」矛盾；且声明自相矛盾 | P2 |
| F11 | 声明不一致 | ④ build_style_profile | 档位判定：文档"任一项有值即招标档"，代码只认 typography.source | P2 |
| F12 | 声明不一致 | ④ 全部脚本 | SKILL §六声明 skills-lock 三级降级自检，9 个脚本均无实现 | P1 |
| F13 | 断链 | skills-lock | lock 记 bid-docx-export=0.2.0，SKILL.md 实读 0.2.1，validate_contract C1 FAIL | P0 |
| F14 | 逻辑错误 | ④ verify_docx.py | 中英文空格检查方向与计划书 §8.7 规则 2 完全相反 | P1 |
| F15 | 断链 | 计划书 §5 | 目录树漏列 export_docx/_common/pdfutil（④）与 build_bid_plan/verify_format_chapters（①） | P1 |
| F16 | 断链 | 计划书 §5 | style-profiles 树列 4 档文件，实际 3 个 + 运行期生成，未注明且漏列 README | P1 |
| F16b | 维护风险 | ④ build_style_profile | BASELINE 硬编码双源，脚本从不读 通用中文基线.yaml，"单一真值见该文件"注释不符 | P2 |
| F17 | 断链 | tests/scan_doc.py | docstring 引用已不存在的 v0.16 文件（实际基准 v0.17） | P2 |
| F18 | 基准澄清 | docs/ | 不存在独立 v0.16 文件，实际基准为 v0.17（信息项，非缺陷） | — |
| F19 | 遗漏 | 计划书 §5 | run_acceptance.py 已实现 498 行，计划书仍标"待建，阶段 2+" | P2 |

---

# 二、逻辑错误（8 项）

## F1｜Markdown 标题前缀剥离普遍少剥 1 字符，docx 与 PDF 两版标题均带前导空格

- **现象**：两个导出脚本均用字符串切片剥离标题前缀，但剥离长度比前缀实际长度少 1，导致标题前残留一个空格：
  - `export_docx.py` L161–168：`#### `→`p[4:]`（应 5）、`### `→`p[3:]`（应 4）、`## `→`p[2:]`（应 3）、`# `→`p[1:]`（应 2），**四级全部残留前导空格**（如 `"# 一、总则"` → `" 一、总则"`）。
  - `assemble_pdf.py` L157–164：`#### `→`para[5:]`（✓）、`### `→`para[4:]`（✓）、`## `→`para[2:]`（❌，应 3）、`# `→`para[2:]`（✓）——二级标题残留空格。
- **证据**：两脚本 L161–168 / L157–164 源码；最小复现 `"## x"[2:] == " x"`。两脚本剥离口径不一致（export 四级全错、assemble 仅二级错）。
- **影响**：正文标题（尤其二/三级、一级）在 docx 与 PDF 两版均带多余前导空格，且两版表现不完全一致。
- **建议**：统一按 `len(prefix)` 计算剥离长度（`para[len(prefix):]`），两脚本共用同一剥离函数，消除逐字硬编码。

## F2｜PDF 装配未替换证据占位符，正文残留 `[[EV:ev-xxx]]`

- **现象**：`assemble_pdf.py` 排正文时未调用 `replace_ev`，正文中的 `[[EV:ev-xxx]]` 占位符原样进入 PDF 文本层。
- **证据**：对 `assemble_pdf.py` grep `replace_ev|EV:` **零命中**；对照 `export_docx.py` L160 在每段正文前调用 `replace_ev(p, ev_map)`。
- **影响**：`投标文件_含附件.pdf` 版本正文直接暴露占位符字样；若评审/存档使用 PDF，等同"占位符残留"废标风险点。
- **建议**：在 PDF 正文排版前对每段执行 `replace_ev`，映射复用 03b.order 装配后的 `ev_map`。

## F3｜章名/章号校验为子串查找，无法证明标题逐字一致

- **现象**：章节加载仅取 id/level，number/title 实际取自各章 frontmatter；`verify_docx.py` 用 `doc_text.find(title, pos)` 子串查找，且未校验 `number` 是否出现在标题行。
- **证据**：`load_chapters_sorted` 与 verify 主流程源码（摘要已核）。
- **影响**：铁律 2"章节名一个标点不改"无机器保证；若正文其他段落恰好包含标题行片段，`find` 命中即放行，章名拼写错误/编号错位检不出。
- **建议**：按标题行做逐字比对（含 number 与 title 拼接形态），而非子串查找；或在正文生成后回读标题行集合与 01c.chapters 做严格 equal。

## F4｜page_number 档位不兑现：恒写页脚居中页码，字号硬编码 9pt

- **现象**：`export_docx.py` 页脚模板恒为居中 `PAGE` 域（L70），`<w:sz w:val="18"/>`（9pt）硬编码；`style-profile.yaml` 中 `typography.page_number` 的 `none`（不编页码）/`header_center`（页眉）/`footer_outer`（页脚外侧）档位全部被忽略。
- **证据**：`export_docx.py` L70、L122–123 sectPr/footerReference；grep 确认 export_docx 内 `page_number` 仅出现在 docstring，未消费样式档字段（对照 `build_style_profile.py` L339–341 已解析并写入 profile，`check_evidence.py` L132–136 也能读回）。
- **影响**：招标明确"不编页码"或"页眉页码"时仍输出页脚居页码，直接触碰排版废标点。
- **建议**：按 style-profile 的 page_number 生成 页眉页脚/无页码/外侧 三种样式变体；页脚字号随正文或基线配置，去掉硬编码 9pt。

## F5｜字体校验形同虚设：parse_font 返回值被丢弃（恒等死代码）

- **现象**：`build_style_profile.py` L307–308 写为 `font = font_raw if parse_font(font_raw) else font_raw`——这是恒等表达式（X if Y else X），无论是否命中白名单，招标原文都原样下传；`parse_font` 结果完全被丢弃，`FONT_WHITELIST` 白名单不起任何过滤作用。
- **证据**：`build_style_profile.py` L147–153（parse_font 定义）、L307–308（恒等三元）。
- **影响**：招标写明"正文仿宋四号"这类描述句时，`font_body` 携带整句进入导出，docx 字体名非法；白名单校验既不能拦截也不记录 warning，与 size/spacing/margins"解析失败回落基线并记 warning"的行为不一致。
- **建议**：去掉恒等三元；解析失败时记 warning 并回落基线（与 L317、L323、L334 一致），只对解析成功的白名单字体照录原文。

## F6｜margins 解析正则紧邻匹配，"2.54cm" 隔断致回落基线

- **现象**：`parse_margins` 对双值形态的正则为 `上下(\d+(?:\.\d+)?)左右(\d+(?:\.\d+)?)`（L119，已先去空格），招标常见写法"上下2.54cm 左右3.17cm"中 `cm` 隔断导致匹配失败，margins 静默回落基线（L334–336 记 warning）。
- **证据**：`build_style_profile.py` L119–122、L332–336。
- **影响**：招标 margin 明示值被忽略而用基线，且需要人工看 warning 才能发现；若基线恰好与招标不同（更常见）则排版不符。
- **建议**：双值正则允许 `(?:cm)?` 后缀；或直接支持"上X下Y左Z右W"单值形态（已支持），双值形态补 cm 容差。

## F7｜暗标标识仅扫 docx，不扫装配后 PDF 文本层

- **现象**：暗标扫描只针对 docx 的正文/页眉页脚/docProps，不检查 `投标文件_含附件.pdf` 的文本层；若证据 PDF 自带页眉单位名、水印或扫描件内文字，暗标泄漏检不出。
- **证据**：`verify_docx.py` 暗标标识步骤仅 `doc_text`/页眉页脚/核心属性；摘要核对确认无 PDF 文本层扫描（contrast：`assemble_pdf.py` 产出 PDF，`verify` 未回读）。
- **影响**：暗标模式下"装配后 PDF 无单位名/人名"的终检要求（计划书 §11.3）实际未覆盖最重要的交付物。
- **建议**：verify 增加对 07_out PDF 文本层的抽取扫描（复用 pdfutil 文本抽取能力），至少覆盖 单位名/人员姓名 关键词。

## F14｜中英文空格检查方向与计划书完全相反

- **现象**：`verify_docx.py` L131 正则 `[\u4e00-\u9fff][A-Za-z]|[A-Za-z][\u4e00-\u9fff]` 匹配的是"**无空格**"情形，并产生 warning「正文存在中英文之间无空格的写法（信息态，不阻断）」；而计划书 §8.7 规则 2 明确"中英文混排**不加空格**"，并写明要落到 verify_docx.py：交付前扫描"**中文+空格+英文**"与"**英文+空格+中文**"的模式。
- **证据**：计划书 v0.17 L1319、L1323；`verify_docx.py` L130–132。
- **影响**：对已合规（无空格）文本反复告警；对真正应检查的"误加空格"（如 `系统采用RAG 技术`）不告警。机检与写作规范完全脱节，规则 2 落地等于零。
- **建议**：按计划书反转正则：扫描 `中文\s+英文|英文\s+中文`，warning 文案改为"中英文之间不应加空格，请删除"。

---

# 三、引用断链与清单不闭合（6 项，其中 F18 为基准澄清/信息项）

## F13｜skills-lock 版本漂移：lock=0.2.0 vs 实读 0.2.1（合同校验红灯）

- **现象**：`skills-lock.json` 记录 `bid-docx-export=0.2.0`（kit v0.2.0-stage1，generated_at 2026-10-21T14:54:30），④ SKILL.md frontmatter 实读 `version: 0.2.1`（mtime 2026-10-21 17:42:20，晚于 lock 生成时间——改版后未刷新 lock）。
- **证据**：实测 `python tests/validate_contract.py` 输出 `FAIL 1 项 [C1] bid-docx-export 版本不一致：lock=0.2.0 实读=0.2.1`；其余 C2–C12 全部 PASS。
- **影响**：交付自检红灯，发布一致性断裂；0.2.1 的实际内容未获 lock 背书。
- **建议**：改版后同步刷新 skills-lock.json；将 C1 纳入发布门禁（见 F12）。

## F15｜计划书目录树不闭合：④ 漏 3 脚本，① 漏 2 脚本

- **现象**：计划书 §5 目录树 ④ 仅列 6 个脚本（build_style_profile / index_evidence / check_evidence / assemble_pdf / scrub_metadata / verify_docx），**漏列 export_docx.py、_common.py、pdfutil.py**——而 `投标文件.docx` 的生成是 §8.4/§11.3 明确验收的必经环节；① 目录树漏列 build_bid_plan.py（v0.4.0 起为总编排器，依次调用 5 个专职脚本 + validate_plan）与 verify_format_chapters.py（v0.3.0 新增保真机检）。
- **证据**：计划书 v0.17 §5 目录树与 `skills/{bid-docx-export,bid-response-plan}/scripts/` 实际文件清单对比；④ SKILL.md/README 自述"按计划书 §5 目录树闭合"与事实不符。
- **影响**：按目录树逐一核验会误判缺件/多件，清单不可作为验收依据。
- **建议**：计划书树补 5 个脚本，或在树中明确"运行期中间脚本"分组。

## F16｜style-profiles 目录树与实际文件树不闭合

- **现象**：计划书 §5 列 `style-profiles/` 下 招标规定.yaml / 甲方模板.yaml / 通用中文基线.yaml / 暗标叠加层.yaml 四档文件；实际 `assets/style-profiles/` 仅 **README.md + 通用中文基线.yaml + 暗标叠加层.yaml** 三个。招标档/甲方模板档由 `build_style_profile.py` 运行期生成到 `07_out/style-profile.yaml`（README 有说明），但计划书树未注明"运行期生成/非预制"，同时未列 README.md（实际多出）。
- **证据**：计划书 L741–745；`assets/style-profiles/` 实际清单；`build_style_profile.py` L484–486 输出 07_out/style-profile.yaml。
- **影响**：按目录树逐一核对时缺 2 文件、多 1 文件；设计本身合理（运行期生成），但文档未同步，仍属引用断链。
- **建议**：计划书树为两个运行期档补注"④ 运行期生成至 07_out/style-profile.yaml，非预制"，并补列 README.md。

## F17｜tests/scan_doc.py docstring 引用已不存在的 v0.16 文件

- **现象**：`tests/scan_doc.py` docstring 仍写"用法：python tests/scan_doc.py docs/投标文件Skill建设计划_v0.16.md"，而 docs/ 已无该文件，实际基准为 v0.17。
- **证据**：scan_doc.py 头部；docs/ 目录、`git --follow` 查无 v0.16 独立历史。
- **影响**：按 docstring 执行即失败，误导使用者。
- **建议**：docstring 更新为 v0.17。

## F18｜审阅基准确认：docs/ 不存在独立 v0.16 文件，实际基准为 v0.17

- **现象**：docs/ 下最高版本为 `投标文件Skill建设计划_v0.17.md`（头部声明"v0.16 冻结基线 + 进展标注同步与验收小节补全"），不存在独立 v0.16 文件（find 曾误报，ls 与 Python glob 均确认）。
- **影响**：本报告全部章节引用以 **v0.17** 为准，即用户要求的"审阅 v0.16"实际审阅的是包含 v0.16 冻结内容的 v0.17 计划书。
- **建议**：无需修复；后续版本演进避免"旧版本文件随改版消失"的命名习惯（影响历史追溯）。

## F19｜计划书仍将 run_acceptance.py 标为"待建"，实际已实现

- **现象**：计划书 §5 tests 目录将 run_acceptance.py 标为"待建，阶段 2+"；实际 `tests/run_acceptance.py` 已实现 498 行（阶段验收驱动器：产物清点、stage↔产物一致性、只读校验器、暗标标识扫描、frontier 指引）。
- **证据**：`python tests/run_acceptance.py --help` 冒烟通过（rc=0，正常输出 usage）；文件头部 docstring 完整声明核查/串联两模式。
- **影响**：计划书落后于实现，验收清单口径模糊（易被误判为"未实现"）。
- **建议**：计划书更新为"已实现（阶段 4）"并在 §11 给出验收命令。

---

# 四、与 SKILL/计划书声明不一致（4 项）

## F8｜出口未上闸门：verify_docx 与 scrub_metadata 均未调用 gate()

- **现象**：`_common.gate()` 仅被 `export_docx.py` L178 与 `assemble_pdf.py` L371 调用；出口校验器 `verify_docx.py`（写 `stage=exported` 的入口）与元数据清理器 `scrub_metadata.py` 均不调用 gate。
- **证据**：对 skills/bid-docx-export/scripts/ grep `gate\(` 仅命中上述 3 处。
- **影响**：verify_docx 在写 `stage=exported` 前缺少前置闸门校验；scrub_metadata 清理前不检查上下文状态。纪律出口存在旁路。
- **建议**：verify_docx 写 stage 前与 scrub_metadata 执行前同样调用 gate（或至少执行 stage 前置校验）。

## F10｜附件引用空格口径自相矛盾：输出「见附件A-01」 vs 声明「见附件 A-xx」

- **现象**：`replace_ev` 生成的引用为「见附件A-01」（无空格）；SKILL.md/计划书声明为「见附件 A-xx」（带空格）。
- **证据**：`export_docx.py` L132–160 replace_ev 实现；SKILL.md 示例文本。
- **补充发现（自我矛盾）**：计划书 §8.7 规则 2 要求"中英文混排不加空格"——若严格按规则 2，SKILL 声明中的「附件 A-xx」反而带空格不合规；而代码输出「附件A-01」恰符合规则 2。三处口径两两冲突。
- **影响**：交付物中附件引用与文档声明不一致；同一计划书内部"规则 2"与"示例声明"相互矛盾，规则 2 落地时无法同时满足两者。
- **建议**：统一口径并消除文档内部冲突：若规则 2 为最终规范，则 SKILL 声明示例改为「见附件A-xx」，代码保持现状；否则代码补空格且规则 2 增加"固定术语附件号除外"的例外说明。

## F11｜档位判定口径：文档"任一项有值即招标档" vs 代码只认 source

- **现象**：计划书/文档表述为"01c.typography 任一项有值即招标档"；`build_style_profile.py` L269–278 只认 `typography.source` 字段（tender_required/client_template，否则 baseline）。
- **证据**：文档对应段落；代码 L269–278。
- **影响**：01c 填了 font_body 等项但漏填 source 时，代码按 baseline 处理而文档预期按招标档——三档判定结果可能不同，且无 warning。
- **建议**：统一口径；增加 source 与 typography 是否有值的交叉校验（source 缺失但有值时记 warning 提示回 ① 补填）。

## F12｜skills-lock 自检未实装：声明三级降级，9 个脚本均无实现

- **现象**：SKILL.md §六声明"读 skills-lock.json，版本不匹配三级降级，不阻断"；对 9 个 python 脚本 grep `skills-lock` **零命中**，运行时无任何版本比对（仅 tests/validate_contract.py 做离线校验）。
- **证据**：grep 结果；SKILL.md 声明。
- **影响**：运行时版本漂移无感知、无降级提示，声明形同虚设；与 F13 叠加使 lock 对运行链路约束为零。
- **建议**：在 ④ 入口（_common.gate 或 export_docx）实现 skills-lock 版本比对与降级日志；若短期不实现，删除/改写该声明避免误导。

---

# 五、内容性遗漏与维护风险（2 项）

## F9｜YAML 空列表读回为字符串 "[]"（潜伏缺陷）

- **现象**：自研 `dump_yaml` 对空列表输出 `key: []`（build_style_profile.py L241–243）。若下游以文本/正则而非标准 YAML 解析（如 check_evidence 用正则读 page_limit），`[]` 会被当成字符串而非空列表处理。
- **证据**：dump_yaml 空列表分支；check_evidence.py L132–136 正则读取 style-profile.yaml 的方式。
- **影响**：当前下游尚未消费空列表字段（潜伏）；一旦有消费者按"空列表==False"判断将误判为有值。
- **建议**：为读取侧统一约定：空列表输出 `: []` 即合法；下游解析时显式把 `[]`/`null` 归一到空/None。

## F16b｜通用中文基线双源：BASELINE 硬编码，脚本从不读 yaml

- **现象**：`build_style_profile.py` L47 硬编码 BASELINE 字典，注释写"与 assets/style-profiles/通用中文基线.yaml 保持一致（**单一真值见该文件**）"；但脚本运行时**从不读取该 yaml**（grep 无任何 `open(…通用中文基线.yaml…)`），yaml 只是未消费的文档镜像；L258 TIER_LABEL 自述"③ 通用中文基线（内置）"。
- **证据**：build_style_profile.py L47–52、L258；grep yaml 读取路径零命中（仅 docstring 与输出 dump 提及）。
- **影响**：当前两份逐项一致（已比对，无实际差异），但未来改 yaml 不更新代码→生成样式与文档不一致且无任何告警；"单一真值"注释与实现相反。
- **建议**：二选一——删除"单一真值"注释并注明"运行期真值为代码硬编码、yaml 为文档镜像"；或让脚本实际读取 yaml 作为唯一真值（消除双源）。

---

# 六、正面结论（实测验证，报告可直接采信）

以下结论均经 hash 比对、脚本实测或源码确认，非推断：

1. **交接约定四副本逐字一致**：四份 `references/流水线交接约定.md` sha256 均为 `14e27b5c510a4fd35df8ec04438c83a4`。
2. **共用 schema 多副本一致且与 lock 吻合**：四份 `assets/metadata.schema.json`（md5 `3a76018e3bb199d00a85a75d87cb022d`）、三份 `assets/facts.schema.yaml`（md5 `fdbcf422ad0cd3ae150b4ca3996e1cf2`）、⓪① 两份 `tender-facts.schema.json` 哈希一致；全部 schema sha256 与 skills-lock 记录逐一吻合。
3. **8 条铁律逐字一致**：四份 SKILL.md `<!-- IRONLAWS -->` 区间正文（strip 后）均为 715 字符，difflib 两两比对零差异。
4. **契约校验 C2–C12 全过**：`python tests/validate_contract.py` 仅 C1（F13）FAIL，其余全 PASS（C10 已比对 v0.17 §7 铁律）。
5. **计划书内部自洽**：`python tests/scan_doc.py "docs/投标文件Skill建设计划_v0.17.md"` 实测 D1–D6 全部通过（表格 60 张）。
6. **基线常数与 yaml 当前一致**：build_style_profile.py BASELINE 与 通用中文基线.yaml 逐项一致（仿宋_GB2312 / 12pt / 1.5 / 2 字符 / 2.54–3.17cm / footer_center）。
7. **evidence 链字段衔接非断链**：`check_evidence.py`/`index_evidence.py` 消费的 `source_type`（qualification/waste/scoring/business）、`response_form=scan`、`source_ref` 均由 ① `build_task_cards.py` L128–137 真实产出；`check_evidence.py` 正则读取 style-profile.yaml 的 `page_limit` 与 `build_style_profile.py` 输出格式匹配。
8. **run_acceptance.py 已实现可运行**：`--help` 冒烟 rc=0（F19 仅计划书标记落后）。
9. **① 专职脚本非空壳**：`verify_format_chapters.py`（逐字比对机检，rc 0/1）与 `build_bid_plan.py`（v0.4.0 总编排器）docstring 完整、职责与 SKILL 声明一致。
10. **④ README 与计划书一致**：含"另存为后再编辑"天坑提示，§8.8.3 四条操作要求照录。
11. **② 常见错误.md 专属反例合规**：文末"反例 9/10（②）"确实落在「## 本技能专属」节下（L83–93），公共 8 条未被增删改（①③④ 公共区逐字一致）。

---

# 七、修复优先级建议

**P0（导出正确性与发布一致性，最迟交付前必修）**
- F2 PDF 装配未替换 EV 占位符
- F4 page_number 档位不兑现（不编页码/页眉页码被忽略）
- F13 skills-lock 版本漂移（C1 红灯）

**P1（验收一致性与暗标安全）**
- F1 标题剥离残留空格（docx/PDF 口径不一致）
- F5 字体校验恒等死代码 + 白名单失效
- F7 暗标 PDF 文本层不扫描
- F8 verify/scrub 出口未上 gate
- F12 skills-lock 运行时自检未实装
- F14 中英文空格检查方向相反
- F15 / F16 目录树与文件树不闭合

**P2（加固与维护）**
- F3 章名弱校验、F6 margins cm 容差、F9 YAML 空列表、F10 空格口径自相矛盾、F11 档位判定口径、F16b 基线双源、F17 scan_doc docstring、F19 计划书版本标记

---

# 八、审阅边界与说明

- 审阅方式为**静态源码审阅 + 最小复现 + 目标实测**（validate_contract / scan_doc / run_acceptance --help / hash 比对），未对五技能做真实投标项目全链路端到端演练；报告内已区分"确认缺陷"与"维护风险/潜伏项"。
- 本报告聚焦用户要求的四类：逻辑错误、引用断链、与计划书不一致、内容性遗漏；排版美观、文案风格等不在审阅范围。
- 计划书引用章节号均以 **v0.17** 为准（F18）。
- 所有"待确认"表述已在正文标注确认方式；凡标注"实测/复现/哈希"的结论均可按第六节命令复现。