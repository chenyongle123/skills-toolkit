# style-profiles/（样式档）

本目录存放 ④ 的**内置样式档**与档位说明，由 `bid-docx-export` v0.2.0 起生效。

| 文件 | 角色 |
|---|---|
| `通用中文基线.yaml` | 排版第③档（内置基线）：仿宋_GB2312／正文小四 12pt／1.5 倍行距／首行缩进 2 字符／页边距上下 2.54cm 左右 3.17cm／页码页脚居中。仅当招标未提任何排版要求时整体生效；招标档个别项空值时**仅该项**回落基线 |
| `暗标叠加层.yaml` | **不是第四档**：与 `bid_mode=blind` 绑定的正交叠加层（无页眉页脚单位名/无 LOGO/属性作者清空/正文无投标人标识），叠加于任一生效档位之上 |

运行期产物 `07_out/style-profile.yaml` 由 `scripts/build_style_profile.py` 生成：
- 招标规定档＝从 `01c.typography` **生成而非手写**（逐项取招标值，空值项回落基线并记入 sources）
- 甲方模板档＝`--template <docx>` 解析模板样式生成
- 产物契约见 `assets/style-profile.schema.json`（④ 单副本，不进 skills-lock）
