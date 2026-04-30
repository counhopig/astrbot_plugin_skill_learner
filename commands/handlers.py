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
    
    async def cmd_learn(self, event: AstrMessageEvent, args: list) -> str:
        """开始学习模式"""
        user_id = event.get_sender_id()
        
        existing = self.storage.get_active_session(user_id)
        if existing and existing.state == LearningState.LISTENING.value:
            return "你已经在学习模式中了。直接发送内容，我会记录。发送 `/skill_save <名称>` 保存，或 `/skill_cancel` 取消。"
        
        session = self.storage.create_session(user_id)
        return (
            f"已进入学习模式（会话: {session.session_id}）"
            f"\n请发送你想要我学习的内容。"
            f"\n完成后发送 `/skill_save <skill名称>` 保存为 Skill。"
            f"\n或发送 `/skill_cancel` 取消。"
        )
    
    async def cmd_cancel(self, event: AstrMessageEvent) -> str:
        """取消学习模式"""
        user_id = event.get_sender_id()
        existing = self.storage.get_active_session(user_id)
        
        if not existing or existing.state != LearningState.LISTENING.value:
            return "当前没有进行中的学习会话。"
        
        self.storage.end_session(user_id)
        return f"已取消学习会话（{existing.session_id}）。"
    
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
            return "还没有保存任何 Skill。发送 `/skill_learn` 开始学习并保存。"
        
        lines = [f"=== 已保存的 Skills（共 {len(skills)} 个） ==="]
        for i, skill in enumerate(skills, 1):
            type_emoji = {
                SkillType.WORKFLOW.value: "📋",
                SkillType.KNOWLEDGE.value: "📚",
                SkillType.TOOL.value: "🔧",
                SkillType.PROMPT.value: "📝",
            }.get(skill.skill_type, "📄")
            
            lines.append(
                f"\n{i}. {type_emoji} {skill.display_name or skill.name}"
                f"\n   类型: {skill.skill_type} | 创建于: {skill.created_at_str}"
                f"\n   描述: {skill.description[:60]}..." if len(skill.description) > 60 else f"\n   描述: {skill.description}"
            )
        
        lines.append("\n使用 `/skill_view <名称>` 查看详情，`/skill_export <名称>` 导出为 zip。")
        return "\n".join(lines)
    
    async def cmd_view(self, event: AstrMessageEvent, name: str) -> str:
        """查看指定 Skill 的内容"""
        skill = self.storage.get_skill(name)
        if not skill:
            return f"未找到 Skill: {name}。使用 `/skill_list` 查看所有 Skill。"
        
        content = self.storage.get_skill_md(name)
        if not content:
            return f"Skill '{name}' 存在但内容读取失败。"
        
        preview = content[:800] + "..." if len(content) > 800 else content
        
        return (
            f"=== {skill.display_name or skill.name} ==="
            f"\n名称: {skill.name}"
            f"\n类型: {skill.skill_type}"
            f"\n标签: {', '.join(skill.tags) if skill.tags else '无'}"
            f"\n创建于: {skill.created_at_str}"
            f"\n\n--- 内容预览 ---\n{preview}"
        )
    
    async def cmd_delete(self, event: AstrMessageEvent, name: str) -> str:
        """删除指定 Skill（同时从 AstrBot skills 目录移除）"""
        skill = self.storage.get_skill(name)
        if not skill:
            return f"未找到 Skill: {name}。"

        # 从插件目录删除
        success = self.storage.delete_skill(name)
        # 从 AstrBot skills 目录删除
        undeployed = self.storage.undeploy_from_astrbot(name)

        msg = f"已删除 Skill: {skill.display_name or name}。"
        if undeployed:
            msg += "\n同时已从 AstrBot 中移除。"
        return msg
    
    async def cmd_export(self, event: AstrMessageEvent, name: str) -> str:
        """导出 Skill 为 zip"""
        skill = self.storage.get_skill(name)
        if not skill:
            return f"未找到 Skill: {name}。"
        
        export_dir = self.storage.data_dir / "exports"
        zip_path = self.storage.export_skill_zip(name, export_dir)
        
        if zip_path:
            return (
                f"Skill '{skill.display_name or name}' 已导出为 zip。"
                f"\n文件路径: {zip_path}"
                f"\n你可以在 AstrBot 管理面板的 Skills 页面上传此 zip 文件。"
            )
        return f"导出 Skill '{name}' 失败。"
    
    async def cmd_help(self, event: AstrMessageEvent) -> str:
        """帮助信息"""
        return (
            "=== Skill 自动学习器 ==="
            "\n\n📖 学习命令:"
            "\n  /skill_learn — 进入学习模式，开始记录内容"
            "\n  /skill_save [名称] — 保存学习内容为 Skill"
            "\n  /skill_cancel — 取消当前学习会话"
            "\n\n📂 管理命令:"
            "\n  /skill_list — 列出所有已保存的 Skills"
            "\n  /skill_view <名称> — 查看 Skill 内容"
            "\n  /skill_delete <名称> — 删除 Skill"
            "\n  /skill_export <名称> — 导出为 zip（可上传 AstrBot）"
            "\n\n💡 快捷触发:"
            "\n  发送'记住这个'、'保存为skill'、'学习一下'等关键词"
            "\n  可直接触发学习模式。"
        )
