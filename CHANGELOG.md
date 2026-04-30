# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/lang/zh-CN/spec/v2.0.0.html).

## [Unreleased]

## [1.1.0] - 2026-05-01

### Added
- 短别名指令：`/sl`、`/ss`、`/sc`、`/st`、`/sh`、`/skills`，降低移动端输入门槛
- `/skill_status` 命令：查看当前学习进度和状态，带鼓励话术
- 群聊隔离机制：群聊和私聊的学习会话独立，避免误触发干扰
- 首次 Skill 保存庆祝提示：强化用户的正向反馈体验
- 管理员权限控制：`/skill_delete` 仅限管理员使用

### Changed
- 错误提示全面优化：从 CLI 风格改为对话式引导，降低认知负担
- 学习模式聚合回复：只在关键节点（1/3/5/10/15 条）发送提示，避免群聊刷屏
- `/skill_save` 名称参数改为可选，AI 自动生成名称兜底
- `cmd_list()` 列表格式优化：更轻量的排版，修复描述截断 bug
- `cmd_view()` 智能截断：在段落边界截断预览内容
- 保存前增加 LLM 等待提示（预计 10-30 秒），消除用户等待焦虑
- LLM 未配置 / 调用失败时，给出更友好的错误说明

### Fixed
- `cmd_list()` 中描述截断条件表达式 bug
- `cmd_view()` 在群聊/私聊中缺失 Skill 时的提示改进

## [1.0.0] - 2026-05-01

### Added
- 初始版本发布
- 自动学习模式：检测关键词（如"记住这个"、"学习一下"）自动进入学习状态
- 命令触发学习：`/skill_learn` 手动开始学习会话
- AI 驱动的 Skill 生成：调用 LLM 自动分析对话内容并生成 `SKILL.md`
- Skill 管理：列出、查看、删除、导出已保存的 Skills
- AstrBot 兼容导出：一键导出为 zip，可直接上传到 AstrBot 管理面板的 Skills 页面
- 四种 Skill 类型支持：工作流 (workflow)、知识 (knowledge)、工具 (tool)、提示词 (prompt)
- 配置项支持：自动触发关键词、单次学习最大消息数、启用/禁用关键词自动触发
- 符合 [Anthropic Skills](https://docs.astrbot.app/use/skills.html) / [agentskills.io](https://agentskills.io) 标准

### Notes
- 依赖 AstrBot >= v4.13.0（需要 Skills 支持）
- 依赖 aiofiles>=23.0.0

[Unreleased]: https://github.com/counhopig/astrbot_plugin_skill_learner/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/counhopig/astrbot_plugin_skill_learner/releases/tag/v1.1.0
[1.0.0]: https://github.com/counhopig/astrbot_plugin_skill_learner/releases/tag/v1.0.0
