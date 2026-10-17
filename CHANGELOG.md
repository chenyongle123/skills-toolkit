# Changelog

本仓库所有技能的版本变更记录。格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [SemVer](https://semver.org/lang/zh-CN/)。

Tag 约定：技能版本 tag 为 `技能名/vX.Y.Z`；仓库级变更 tag 为 `repo/vX.Y.Z`。

## [repo/v1.1.0] - 2026-10-17

### Added

- 新增仓库级 `docs/` 目录，收纳与技能运行无关的开发设计文档

### Changed

- 开发过程文档迁出技能包：`未来升级方向备忘` 脱敏后移至 `docs/`，`v8行为验证报告` 删除（结论已提炼进规则变更记录）

## [tender-document-review/v1.1.0] - 2026-10-17

### Changed

- **发布包净化**：移除 `references/v8行为验证报告.md`（含真实项目名与本地绝对路径，违反"个体内容不进技能"原则）与 `references/未来升级方向备忘.md`（开发决策记录，非运行所需）；技能包现仅含 SKILL.md + README + 3 份运行必需参考文件
- **版本体系单轨化**：取消"技能版本 / 规则版本"双轨编号，技能版本号 `1.1.0` 即唯一版本；`判词库.md` 的「版本记录」改为「规则变更记录（历史，仅供追溯）」，不再启用 vN 编号
- README 目录清单与实际文件对齐

## [repo/v1.0.0] - 2026-10-17

### Added

- 仓库骨架：`skills/` 目录结构、README、LICENSE（CC BY-NC 4.0）、CHANGELOG、.gitignore
- 初始收录三个技能（均 v1.0.0，见下）

## [tender-document-review/v1.0.0] - 2026-10-15

### Added

- 投标方视角招标文件审查技能首发：七类结构化清单（时间节点与流程/资格条件/废标情形/评标定标/保证金商务/合同约束/形式程序）
- 内部规则版本 v9（`references/判词库.md`）
- 清单模板、法定情形核对卡、行为验证报告

## [business-contract-review/v1.0.0] - 2026-10-10

### Added

- 中国法商务合同审核技能首发：四类合同（施工/EPC分包、物资采购、技术服务、招标代理/劳务）条款级审查
- 红黄绿三级风险分级 + redline 修改建议 + 谈判策略
- 通用条款叠加检查、成套文件解释顺序、内部一致性核查
- 第九步交付前收口自检（法律类 11 项）

## [delivery-audit/v1.0.0] - 2026-10-10

### Added

- 交付前审查技能首发：五条铁律（L1 记忆非证据 ~ L5 校验优先）
- 四段闸门（CLAIM → EVIDENCE → FRESH+INDEP → REDOUBT）
- 三态输出（✅/⚠️/❌）与四领域清单（数据/文档/电气/法律）
