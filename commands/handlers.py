"""
命令处理器：所有用户命令的响应逻辑
"""

from pathlib import Path
from typing import Optional

from astrbot.api.event import AstrMessageEvent
from astrbot.api import logger

from ..storage import SkillStorage
from ..models import LearnedSkill, LearningSession, LearningState, SkillType
from ..engine.learner import LearningEngine


class CommandHandlers:
    def __init__(self, storage: SkillStorage, learner: LearningEngine):
        self.storage = storage
        self.learner = learner
    
    # ---------- 学习命令 ----------
    
    async def cmd_learn(self, event: AstrMessageEvent, args: list, group_id: str = "") -> str:
        """开始学习模式"""
        user_id = event.get_sender_id()
        
        existing = self.storage.get_active_session(user_id, group_id)
        if existing and existing.state == LearningState.LISTENING.value:
            return "📖 你已经在学习模式中了~\n直接发送内容，我会记录。\n✅ 完成后发送 `/skill_save <名称>` 保存\n❌ 发送 `/skill_cancel` 取消"
        
        session = self.storage.create_session(user_id, group_id)
        return (
            f"📖 已进入学习模式！（会话: {session.session_id}）\n"
            f"请发送你想要我学习的内容~\n"
            f"✅ 完成后发送 `/skill_save <名称>` 保存\n"
            f"❌ 发送 `/skill_cancel` 取消"
        )
    
    async def cmd_cancel(self, event: AstrMessageEvent, group_id: str = "") -> str:
        """取消学习模式"""
        user_id = event.get_sender_id()
        existing = self.storage.get_active_session(user_id, group_id)
        
        if not existing or existing.state != LearningState.LISTENING.value:
            return "📭 当前没有进行中的学习会话。"
        
        self.storage.end_session(user_id, group_id)
        return f"📭 已取消学习会话（{existing.session_id}）。"
    
    async def cmd_save(self, event: AstrMessageEvent, name: Optional[str] = None) -> str:
        """保存当前学习内容为 Skill（需要后续 LLM 生成内容）"""
        user_id = event.get_sender_id()
        session = self.storage.get_active_session(user_id)
        
        if not session or session.state != LearningState.LISTENING.value:
            return "当前没有进行中的学习会话。请先发送 `/skill_learn` 开始学习。"
        
        if not session.messages:
            return "学习会话中还没有内容。请发送一些内容后再保存。"
        
        session.state = LearningState.CONFIRMING.value
        self.storage.update_session(session)
        
        if name:
            session.proposed_name = name
            self.storage.update_session(session)
        
        return (
            f"准备保存学习会话（{len(session.messages)} 条消息）"
            f"\n请稍等，我正在分析内容并生成 Skill..."
        )
    
    # ---------- Skill 管理命令 ----------
    
    async def cmd_list(self, event: AstrMessageEvent) -> str:
        """列出所有已保存的 Skills"""
        skills = self.storage.list_skills()
        
        if not skills:
            return "📭 还没有保存任何 Skill 呢~\n发送 `/skill_learn` 或说「学习一下」，就可以开始教 Bot 新知识啦！"
        
        lines = [f"📚 已保存 {len(skills)} 个 Skill："]
        for i, skill in enumerate(skills, 1):
            type_emoji = {
                SkillType.WORKFLOW.value: "📋",
                SkillType.KNOWLEDGE.value: "📚",
                SkillType.TOOL.value: "🔧",
                SkillType.PROMPT.value: "📝",
            }.get(skill.skill_type, "📄")
            
            desc = skill.description[:40] + "..." if len(skill.description) > 40 else skill.description
            lines.append(f"{i}. {type_emoji} {skill.display_name or skill.name} ({skill.skill_type})")
        
        lines.append("\n💡 查看详情：`/skill_view <名称>` | 导出：`/skill_export <名称>`")
        return "\n".join(lines)
    
    async def cmd_view(self, event: AstrMessageEvent, name: str) -> str:
        """查看指定 Skill 的内容"""
        skill = self.storage.get_skill(name)
        if not skill:
            return f"❓ 未找到 Skill `{name}`\n发送 `/skill_list` 看看已保存的所有 Skill 吧~"
        
        content = self.storage.get_skill_md(name)
        if not content:
            return f"⚠️ Skill `{name}` 存在但内容读取失败，可能是文件损坏了。"
        
        # 智能截断：尽量在段落或代码块边界截断
        preview = content
        if len(content) > 800:
            # 尝试在最后一个换行处截断
            trunc = content[:800]
            last_break = trunc.rfind("\n")
            if last_break > 600:
                preview = trunc[:last_break] + "\n\n...（内容较长，完整版已保存）"
            else:
                preview = trunc + "..."
        
        return (
            f"📄 **{skill.display_name or skill.name}**\n"
            f"类型: {skill.skill_type} | 标签: {', '.join(skill.tags) if skill.tags else '无'}\n"
            f"创建于: {skill.created_at_str}\n"
            f"\n---\n{preview}"
        )
    
    async def cmd_delete(self, event: AstrMessageEvent, name: str) -> str:
        """删除指定 Skill（同时从 AstrBot skills 目录移除）"""
        skill = self.storage.get_skill(name)
        if not skill:
            return f"❓ 未找到 Skill `{name}`\n发送 `/skill_list` 查看所有已保存的 Skill~"

        # 从插件目录删除
        success = self.storage.delete_skill(name)
        # 从 AstrBot skills 目录删除
        undeployed = self.storage.undeploy_from_astrbot(name)

        msg = f"🗑️ 已删除 Skill: {skill.display_name or name}"
        if undeployed:
            msg += "\n同时已从 AstrBot 中移除。"
        return msg
    
    async def cmd_export(self, event: AstrMessageEvent, name: str) -> str:
        """导出 Skill 为 zip"""
        skill = self.storage.get_skill(name)
        if not skill:
            return f"❓ 未找到 Skill `{name}`\n发送 `/skill_list` 查看所有已保存的 Skill~"
        
        export_dir = self.storage.data_dir / "exports"
        zip_path = self.storage.export_skill_zip(name, export_dir)
        
        if zip_path:
            return (
                f"📦 Skill `{skill.display_name or name}` 已导出为 zip！\n"
                f"文件路径: `{zip_path}`\n"
                f"\n💡 你可以在 AstrBot 管理面板的 Skills 页面上传此 zip 文件。"
            )
        return f"⚠️ 导出 Skill `{name}` 失败了，请检查文件权限后重试。"
    
    async def cmd_help(self, event: AstrMessageEvent, in_learning: bool = False) -> str:
        """帮助信息"""
        if in_learning:
            return (
                "📖 你正在学习模式中！\n"
                "直接发送内容，我会逐条记录。\n"
                "\n✅ 完成后发送 `/skill_save <名称>` 保存"
                "\n❌ 发送 `/skill_cancel` 取消学习"
                "\n📊 发送 `/skill_status` 查看当前进度"
            )
        
        return (
            "🎓 **Skill 自动学习器** —— 让 Bot 越聊越聪明\n"
            "\n📖 **快速开始：**"
            "\n  说「学习一下」或发送 `/skill_learn` 进入学习模式"
            "\n  发送你想教给 Bot 的内容"
            "\n  发送 `/skill_save 名称` 保存为 Skill"
            "\n"
            "\n📋 **学习命令：**"
            "\n  `/skill_learn` / `/学习` / `/sl` — 开始学习"
            "\n  `/skill_save <名称>` / `/ss` — 保存 Skill"
            "\n  `/skill_cancel` / `/sc` — 取消学习"
            "\n  `/skill_status` / `/st` — 查看学习进度"
            "\n"
            "\n📂 **管理命令：**"
            "\n  `/skill_list` / `/skills` — 列出所有 Skill"
            "\n  `/skill_view <名称>` — 查看详情"
            "\n  `/skill_delete <名称>` — 删除 Skill（仅管理员）"
            "\n  `/skill_export <名称>` — 导出为 zip"
            "\n"
            "\n💡 **快捷触发：**"
            "\n  「记住这个」「保存为skill」「学习一下」等关键词"
        )
    
    async def cmd_status(self, event: AstrMessageEvent, session: Optional[LearningSession] = None) -> str:
        """查看当前学习状态"""
        if not session or session.state != LearningState.LISTENING.value:
            return "📭 当前没有进行中的学习会话。\n发送 `/skill_learn` 或说「学习一下」开始吧~"
        
        progress = len(session.messages)
        max_turns = 20  # 默认值，实际应从配置读取
        
        if progress == 0:
            return (
                f"📖 学习会话进行中（ID: {session.session_id}）\n"
                f"已记录: 0 条消息\n"
                f"\n请发送你想让我学习的内容~"
            )
        
        # 根据进度给不同的鼓励话术
        encouragements = {
            1: "好的，开始记录了！",
            3: "已经记录了不少内容了，继续加油！",
            5: "看起来你在教我一件很有趣的事情~",
            10: "哇，已经记录了 10 条了！内容很充实呢！",
        }
        
        msg = encouragements.get(progress, f"已记录 {progress} 条消息")
        
        return (
            f"📖 学习会话进行中（ID: {session.session_id}）\n"
            f"已记录: {progress}/{max_turns} 条消息\n"
            f"\n{msg}\n"
            f"\n✅ 发送 `/skill_save <名称>` 保存"
            f"\n❌ 发送 `/skill_cancel` 取消"
        )
