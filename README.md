# AstrBot Skill Learner

AstrBot 插件 —— **自动学习对话并保存为可复用的 Skill**

受 [Hermes Agent](https://github.com/NousResearch/hermes-agent) 的启发，本插件让 AstrBot 能够从与用户的对话中自动学习知识、工作流和提示词模板，并将其保存为符合 [Anthropic Skills](https://docs.astrbot.app/use/skills.html) / [agentskills.io](https://agentskills.io) 标准的 Skill 文件，可直接在 AstrBot 中使用。

## 功能特性

- 自动学习模式：检测关键词（如"记住这个"、"学习一下"）自动进入学习状态
- 命令触发学习：`/skill_learn` 手动开始学习会话
- AI 驱动的 Skill 生成：调用 LLM 自动分析对话内容并生成 `SKILL.md`
- Skill 管理：列出、查看、删除、导出已保存的 Skills
- AstrBot 兼容导出：一键导出为 zip，可直接上传到 AstrBot 管理面板的 Skills 页面
- 四种 Skill 类型支持：工作流 (workflow)、知识 (knowledge)、工具 (tool)、提示词 (prompt)

## 安装

将本插件放入 AstrBot 的 `data/plugins/` 目录下，重启 AstrBot 即可自动加载。

或通过插件市场安装：
```
plugin i https://github.com/counhopig/astrbot_plugin_skill_learner
```

## 依赖

- `aiofiles>=23.0.0`
- AstrBot >= v4.13.0（需要 Skills 支持）

## 使用说明

### 快速开始

1. **自动触发**：发送包含"记住这个"、"学习一下"等关键词的消息
2. **手动触发**：发送 `/skill_learn` 或 `/学习`
3. **发送内容**：在学习模式下发送你想要 Bot 学习的内容
4. **保存 Skill**：发送 `/skill_save <名称>` 保存
5. **导出使用**：发送 `/skill_export <名称>` 导出为 zip，上传到 AstrBot Skills 页面

### 命令列表

| 命令 | 别名 | 说明 |
|------|------|------|
| `/skill_learn` | `/学习` | 进入学习模式，开始记录内容 |
| `/skill_save <名称>` | - | 保存学习内容为 Skill |
| `/skill_cancel` | `/取消学习` | 取消当前学习会话 |
| `/skill_list` | `/技能列表` | 列出所有已保存的 Skills |
| `/skill_view <名称>` | - | 查看指定 Skill 的内容 |
| `/skill_delete <名称>` | - | 删除指定 Skill |
| `/skill_export <名称>` | - | 导出为 AstrBot 兼容的 zip |
| `/skill_help` | `/技能帮助` | 显示帮助信息 |

### 配置项

在 AstrBot WebUI 的插件配置页面可调整：

- **自动触发关键词**：自定义触发学习模式的关键词列表
- **单次学习最大消息数**：防止会话过长（默认 20）
- **启用关键词自动触发**：关闭后只能通过命令进入学习模式

## Skill 存储位置

插件数据存储在：
```
data/plugin_data/astrbot_plugin_skill_learner_counhopig/
├── sessions/      # 学习会话记录
├── skills/        # 已生成的 Skills（每个 Skill 一个文件夹）
│   └── skill-name/
│       ├── SKILL.md
│       └── .skill_meta.json
└── exports/       # 导出的 zip 文件
```

## 工作原理

```
用户发送内容
    ↓
检测触发关键词 或 /skill_learn 命令
    ↓
进入学习模式，记录对话消息
    ↓
用户发送 /skill_save
    ↓
调用 LLM 分析内容（总结、分类、命名）
    ↓
调用 LLM 生成 SKILL.md（符合 Anthropic Skills 规范）
    ↓
保存到 skills/ 目录
    ↓
可选：/skill_export 导出为 zip
    ↓
上传到 AstrBot Skills 页面使用
```

## 参考

- [Hermes Agent](https://github.com/NousResearch/hermes-agent) - Nous Research 的开源 Agent 框架
- [Anthropic Skills](https://docs.astrbot.app/use/skills.html) - AstrBot Skills 使用文档
- [agentskills.io](https://agentskills.io) - Skill 开放标准规范

## License

MIT
