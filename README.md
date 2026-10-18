# Skills Toolkit

中文法律/工程交付场景的 AI Agent 技能集（WorkBuddy / Claude Code 兼容 SKILL.md 格式）。

## 技能一览

| 技能 | 版本 | 定位 |
|---|---|---|
| [tender-document-review](skills/tender-document-review/) | v1.5.0 | 投标方视角招标文件审查：将限制性条款规范、不漏、可追溯地提取为七类结构化清单 |
| [business-contract-review](skills/business-contract-review/) | v1.0.0 | 中国法商务合同审核：四类合同条款级审查，红黄绿分级 + 可用 redline 修改建议 |
| [delivery-audit](skills/delivery-audit/) | v1.1.3 | 交付前审查闸门：五条铁律 + 四段闸门 + 三态输出（✅/⚠️/❌） |
| [bid-response-plan](skills/bid-response-plan/) | v0.6.0 | ① 投标响应策划：任务卡、目录骨架、商务表框架（v0.6.0 阶段 1 已实装） |
| [bid-compliance-check](skills/bid-compliance-check/) | v0.3.2 | ② 投标合规自检：②-A 覆盖检查已实装（阶段 1）；②-B 响应检查随阶段 2 |
| [bid-technical-proposal](skills/bid-technical-proposal/) | v0.1.1 | ③ 技术标正文：逐章成文，技术路线须过 G4（骨架，阶段 2 交付） |
| [bid-docx-export](skills/bid-docx-export/) | v0.1.1 | ④ 排版导出：样式档、证据装配、元数据清理（骨架，阶段 3 交付） |

## 技能关系

```
tender-document-review ─────┐
                            ├──> delivery-audit（交付前审查闸门，可点名加载领域清单）
business-contract-review ───┘
```

- `delivery-audit` 是通用收口闸门，任何产出结论/数值/交付物的任务均适用
- **触发边界**：`delivery-audit` 只做交付前审查，**不替代领域执行技能**；用户请求本身是领域任务
  （如编写投标文件、审核合同）时，由对应领域技能（① bid-response-plan 等）执行，
  `delivery-audit` 在其产出交付物时触发，不因任务名称抢先加载
- 两个审查类技能自带内部自检步骤；环境中存在 `delivery-audit` 且用户点名时可加大审查力度
- **lock 管控边界**：`skills-lock.json` 仅锁定投标套件五技能（⓪①②③④）与 7 类契约 schema 的版本/hash；
  `business-contract-review` 与 `delivery-audit` 为**套件外挂技能**（通用收口与合同审查），
  不纳入 lock，各自独立版本化

## 仓库结构

```
skills/<技能名>/   技能包（仅含运行必需文件：SKILL.md、README、references/）
docs/              仓库级文档（开发设计备忘等，不属于任何技能包）
```

> 原则：技能包内只放 Agent 运行所需内容；开发过程记录、验证报告、项目个案一律不入包。

## 安装

将对应技能目录复制到 Agent 的技能目录即可：

```bash
# WorkBuddy 用户级技能目录
cp -r skills/tender-document-review ~/.workbuddy/skills/
cp -r skills/business-contract-review ~/.workbuddy/skills/
cp -r skills/delivery-audit ~/.workbuddy/skills/
```

## 版本管理约定
- 每个技能独立版本号（见各自 `SKILL.md` 的 `version:` 字段）
- Git tag 采用 `技能名/vX.Y.Z` 前缀，如 `tender-document-review/v1.1.0`
- 仓库级变更（README/CI/新增技能）使用 `repo/vX.Y.Z`
- 版本升级记录见 [CHANGELOG.md](CHANGELOG.md)

## 许可证

本项目采用 [CC BY-NC 4.0](LICENSE)（署名-非商业性使用 4.0 国际）。

- ✅ 可自由复制、修改、分发（需署名）
- ❌ 不得用于商业目的
