"""
AstrBot Skill Learner Plugin
自动学习对话内容并保存为可复用的 Anthropic Skill
"""

import asyncio
from pathlib import Path
from typing import Optional

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger

from .storage import SkillStorage
from .models import LearningSession, LearningState, LearnedSkill, LearningConfig
from .engine.learner import LearningEngine
from .commands.handlers import CommandHandlers


@register(
    "astrbot_plugin_skill_learner_counhopig",
    "counhopig",
    "AstrBot Skill Learner —— 自动学习对话并保存为可复用 Skill",
    "1.0.0",
)
class SkillLearnerPlugin(Star):
    def __init__(self, context: Context, config: dict | None = None):
        super().__init__(context)
        self.raw_config = config or {}
        
        # 数据目录
        self.data_dir = Path(__file__).parent / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化配置
        self.cfg = LearningConfig(
            auto_trigger_keywords=self.raw_config.get(
                "auto_trigger_keywords",
                ["记住这个", "保存为skill", "学习一下", "记下来", "记住", "保存技能", "学一下", "learn this"]
            ),
            max_learning_turns=self.raw_config.get("max_learning_turns", 20),
            enable_auto_learn=self.raw_config.get("enable_auto_learn", True),
            enable_proactive_suggest=self.raw_config.get("enable_proactive_suggest", True),
            proactive_threshold=self.raw_config.get("proactive_threshold", 3),
        )
        self.auto_deploy = self.raw_config.get("auto_deploy_to_astrbot", True)
        
        # 初始化存储和引擎
        self.storage = SkillStorage(self.data_dir)
        self.learner = LearningEngine()
        self.cmd = CommandHandlers(self.storage, self.learner)
        
        logger.info("[SkillLearner] 插件已加载")

    # ============================================================
    # 生命周期
    # ============================================================

    async def initialize(self):
        logger.info("[SkillLearner] 初始化完成")

    async def terminate(self):
        logger.info("[SkillLearner] 插件已卸载")

    # ============================================================
    # 命令接口
    # ============================================================

    @filter.command("skill_learn", alias={"学习", "开始学习"})
    async def skill_learn(self, event: AstrMessageEvent):
        """进入学习模式，开始记录内容"""
        result = await self.cmd.cmd_learn(event, [])
        yield event.plain_result(result)

    @filter.command("skill_cancel", alias={"取消学习", "取消记录"})
    async def skill_cancel(self, event: AstrMessageEvent):
        """取消当前学习会话"""
        result = await self.cmd.cmd_cancel(event)
        yield event.plain_result(result)

    @filter.command("skill_save")
    async def skill_save(self, event: AstrMessageEvent):
        """保存学习内容为 Skill（需要指定名称）"""
        message_str = event.message_str.strip()
        parts = message_str.split(maxsplit=1)
        name = parts[1].strip() if len(parts) > 1 else None
        
        user_id = event.get_sender_id()
        session = self.storage.get_active_session(user_id)
        
        if not session or session.state != LearningState.LISTENING.value:
            yield event.plain_result("当前没有进行中的学习会话。请先发送 `/skill_learn` 开始学习。")
            return
        
        if not session.messages:
            yield event.plain_result("学习会话中还没有内容。请发送一些内容后再保存。")
            return
        
        # 标记为确认中
        session.state = LearningState.CONFIRMING.value
        if name:
            session.proposed_name = name
        self.storage.update_session(session)
        
        yield event.plain_result(
            f"正在分析 {len(session.messages)} 条消息并生成 Skill，请稍等..."
        )
        
        # 调用 LLM 生成 Skill
        try:
            skill = await self._generate_skill(event, session)
            if skill:
                # 保存到插件目录（备份）
                self.storage.save_skill(skill)
                # 根据配置自动部署到 AstrBot skills 目录
                deployed_path = None
                if self.auto_deploy:
                    deployed_path = self.storage.deploy_to_astrbot(skill)
                self.storage.end_session(user_id)

                msg = (
                    f"Skill 已保存！"
                    f"\n名称: {skill.display_name or skill.name}"
                    f"\n类型: {skill.skill_type}"
                    f"\n描述: {skill.description}"
                )
                if self.auto_deploy:
                    if deployed_path:
                        msg += f"\n\n已自动部署到 AstrBot，现在可以在 Agent 中直接使用了。"
                    else:
                        msg += f"\n\n已保存到插件目录，但自动部署失败（可能无写入权限）。"
                msg += f"\n使用 `/skill_view {skill.name}` 查看完整内容。"
                yield event.plain_result(msg)
            else:
                yield event.plain_result("生成 Skill 失败，请稍后重试。")
        except Exception as e:
            logger.error(f"[SkillLearner] 生成 Skill 失败: {e}")
            yield event.plain_result(f"生成 Skill 时出错: {e}")

    @filter.command("skill_list", alias={"技能列表", "skill列表"})
    async def skill_list(self, event: AstrMessageEvent):
        """列出所有已保存的 Skills"""
        result = await self.cmd.cmd_list(event)
        yield event.plain_result(result)

    @filter.command("skill_view")
    async def skill_view(self, event: AstrMessageEvent):
        """查看指定 Skill 的内容"""
        message_str = event.message_str.strip()
        parts = message_str.split(maxsplit=1)
        
        if len(parts) < 2:
            yield event.plain_result("请指定 Skill 名称。用法: /skill_view <名称>")
            return
        
        result = await self.cmd.cmd_view(event, parts[1].strip())
        yield event.plain_result(result)

    @filter.command("skill_delete")
    async def skill_delete(self, event: AstrMessageEvent):
        """删除指定 Skill"""
        message_str = event.message_str.strip()
        parts = message_str.split(maxsplit=1)
        
        if len(parts) < 2:
            yield event.plain_result("请指定 Skill 名称。用法: /skill_delete <名称>")
            return
        
        result = await self.cmd.cmd_delete(event, parts[1].strip())
        yield event.plain_result(result)

    @filter.command("skill_export")
    async def skill_export(self, event: AstrMessageEvent):
        """导出 Skill 为 zip（AstrBot 兼容格式）"""
        message_str = event.message_str.strip()
        parts = message_str.split(maxsplit=1)
        
        if len(parts) < 2:
            yield event.plain_result("请指定 Skill 名称。用法: /skill_export <名称>")
            return
        
        result = await self.cmd.cmd_export(event, parts[1].strip())
        yield event.plain_result(result)

    @filter.command("skill_help", alias={"技能帮助", "skill帮助"})
    async def skill_help(self, event: AstrMessageEvent):
        """显示 Skill Learner 帮助信息"""
        result = await self.cmd.cmd_help(event)
        yield event.plain_result(result)

    # ============================================================
    # 消息监听（自动触发学习模式）
    # ============================================================

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message_listener(self, event: AstrMessageEvent):
        """监听消息，检测自动触发关键词，记录学习会话内容"""
        user_id = event.get_sender_id()
        msg_text = event.message_str or ""
        
        if not msg_text:
            return
        
        # 忽略本插件的命令消息
        if msg_text.startswith("/skill_"):
            return
        
        # 检查是否在学习模式中
        session = self.storage.get_active_session(user_id)
        if session and session.state == LearningState.LISTENING.value:
            # 记录消息
            session.messages.append({
                "role": "user",
                "content": msg_text,
            })
            self.storage.update_session(session)
            
            # 检查是否超过最大轮数
            if len(session.messages) >= self.cfg.max_learning_turns:
                yield event.plain_result(
                    f"学习会话已达到最大消息数（{self.cfg.max_learning_turns}）。"
                    f"\n请发送 `/skill_save <名称>` 保存，或 `/skill_cancel` 取消。"
                )
            else:
                yield event.plain_result(
                    f"已记录（{len(session.messages)}/{self.cfg.max_learning_turns}）。"
                    f"\n继续发送内容，或发送 `/skill_save <名称>` 保存。"
                )
            return
        
        # 检查自动触发关键词
        if self.cfg.enable_auto_learn:
            if self.learner.check_auto_trigger(msg_text, self.cfg.auto_trigger_keywords):
                session = self.storage.create_session(user_id)
                yield event.plain_result(
                    f"检测到学习意图，已进入学习模式（会话: {session.session_id}）"
                    f"\n请发送你想要我学习的内容。"
                    f"\n完成后发送 `/skill_save <skill名称>` 保存为 Skill。"
                    f"\n发送 `/skill_cancel` 取消。"
                )

    # ============================================================
    # LLM 调用与 Skill 生成
    # ============================================================

    async def _generate_skill(self, event: AstrMessageEvent, session: LearningSession) -> Optional[LearnedSkill]:
        """使用 LLM 分析学习会话并生成 Skill"""
        umo = event.unified_msg_origin
        provider_id = await self.context.get_current_chat_provider_id(umo=umo)
        
        if not provider_id:
            logger.warning("[SkillLearner] 未找到可用的 LLM 提供商")
            return None
        
        # 第一步：分析内容
        analysis_prompt = self.learner.build_analysis_prompt(session)
        try:
            analysis_resp = await self.context.llm_generate(
                chat_provider_id=provider_id,
                prompt=analysis_prompt,
            )
            analysis_text = analysis_resp.completion_text or ""
            analysis = self.learner.parse_analysis_result(analysis_text)
            
            if not analysis:
                logger.warning("[SkillLearner] LLM 分析结果解析失败，使用默认值")
                analysis = {
                    "summary": "用户教授的内容",
                    "skill_type": "knowledge",
                    "proposed_name": session.proposed_name or "learned-skill",
                    "display_name": "学习的技能",
                    "tags": ["user-taught"],
                    "description": "从对话中学习到的内容",
                }
        except Exception as e:
            logger.error(f"[SkillLearner] LLM 分析失败: {e}")
            analysis = {
                "summary": "用户教授的内容",
                "skill_type": "knowledge",
                "proposed_name": session.proposed_name or "learned-skill",
                "display_name": "学习的技能",
                "tags": ["user-taught"],
                "description": "从对话中学习到的内容",
            }
        
        # 使用用户指定的名称或 AI 建议的名称
        skill_name = session.proposed_name or analysis.get("proposed_name", "learned-skill")
        skill_name = self._sanitize_name(skill_name)
        
        display_name = analysis.get("display_name", skill_name)
        skill_type = analysis.get("skill_type", "knowledge")
        description = analysis.get("description", "")
        tags = analysis.get("tags", ["user-taught"])
        
        # 第二步：生成 SKILL.md
        generation_prompt = self.learner.build_skill_generation_prompt(
            session=session,
            skill_type=skill_type,
            name=skill_name,
            display_name=display_name,
            description=description,
            tags=tags,
        )
        
        try:
            gen_resp = await self.context.llm_generate(
                chat_provider_id=provider_id,
                prompt=generation_prompt,
            )
            skill_md = self.learner.parse_skill_md(gen_resp.completion_text or "")
            
            if not skill_md:
                logger.warning("[SkillLearner] LLM 生成 SKILL.md 失败")
                return None
        except Exception as e:
            logger.error(f"[SkillLearner] LLM 生成 SKILL.md 失败: {e}")
            return None
        
        # 创建 Skill 对象
        skill = LearnedSkill(
            name=skill_name,
            display_name=display_name,
            skill_type=skill_type,
            description=description,
            created_by=session.user_id,
            source_session=session.session_id,
            tags=tags,
            skill_md_content=skill_md,
        )
        
        return skill

    @staticmethod
    def _sanitize_name(name: str) -> str:
        """清理 Skill 名称，确保合法"""
        import re
        # 只允许小写字母、数字、连字符、下划线
        name = name.lower().strip().replace(" ", "-").replace("_", "-")
        name = re.sub(r"[^a-z0-9\-]", "", name)
        if not name:
            name = "learned-skill"
        return name[:64]
