# Skills Toolkit

中文法律/工程交付场景的 AI Agent 技能集（WorkBuddy / Claude Code 兼容 SKILL.md 格式）。

## 技能一览

| 技能 | 版本 | 定位 |
|---|---|---|
| [bid-tender-review](skills/bid-tender-review/) | v1.0.0 | 投标方视角招标文件审查：将限制性条款规范、不漏、可追溯地提取为七类结构化清单 |
| [business-contract-review](skills/business-contract-review/) | v1.0.0 | 中国法商务合同审核：四类合同条款级审查，红黄绿分级 + 可用 redline 修改建议 |
| [delivery-audit](skills/delivery-audit/) | v1.0.0 | 交付前审查闸门：五条铁律 + 四段闸门 + 三态输出（✅/⚠️/❌） |

## 技能关系

```
bid-tender-review ──┐
                    ├──> delivery-audit（交付前审查闸门，可点名加载领域清单）
business-contract-review ──┘
```

- `delivery-audit` 是通用收口闸门，任何产出结论/数值/交付物的任务均适用
- 两个审查类技能自带内部自检步骤；环境中存在 `delivery-audit` 且用户点名时可加大审查力度

## 安装

将对应技能目录复制到 Agent 的技能目录即可：

```bash
# WorkBuddy 用户级技能目录
cp -r skills/bid-tender-review ~/.workbuddy/skills/
cp -r skills/business-contract-review ~/.workbuddy/skills/
cp -r skills/delivery-audit ~/.workbuddy/skills/
```

## 版本管理约定

- 每个技能独立版本号（见各自 `SKILL.md` 的 `version:` 字段）
- Git tag 采用 `技能名/vX.Y.Z` 前缀，如 `bid-tender-review/v1.1.0`
- 仓库级变更（README/CI/新增技能）使用 `repo/vX.Y.Z`
- 版本升级记录见 [CHANGELOG.md](CHANGELOG.md)

## 许可证

本项目采用 [CC BY-NC 4.0](LICENSE)（署名-非商业性使用 4.0 国际）。

- ✅ 可自由复制、修改、分发（需署名）
- ❌ 不得用于商业目的
