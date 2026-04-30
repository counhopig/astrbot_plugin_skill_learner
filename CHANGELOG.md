# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/lang/zh-CN/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/counhopig/astrbot_plugin_skill_learner/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/counhopig/astrbot_plugin_skill_learner/releases/tag/v1.0.0
