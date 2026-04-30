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

    # ========== 权限检查 ==========

    def _is_admin(self, event: AstrMessageEvent) -> bool:
        """检查发送者是否为管理员"""
        try:
            sender_id = event.get_sender_id()
            # 优先检查是否为 AstrBot 平台管理员
            if hasattr(event, "is_admin") and event.is_admin():
                return True
            # 通过 context 检查权限
            if self.context and hasattr(self.context, "get_group_admin"):
                admins = self.context.get_group_admin(event.unified_msg_origin)
                if admins and sender_id in admins:
                    return True
        except Exception:
            pass
        return False

    @staticmethod
    def _get_group_id(event: AstrMessageEvent) -> str:
        """安全获取群聊ID，私聊返回空字符串"""
        try:
            if hasattr(event, "get_group_id"):
                return event.get_group_id() or ""
        except Exception:
            pass
        return ""

    # ========== 学习命令 ==========

    @filter.command("skill_learn", alias={"学习", "开始学习", "sl"})
    async def skill_learn(self, event: AstrMessageEvent):
        """进入学习模式，开始记录内容"""
        group_id = self._get_group_id(event)
        result = await self.cmd.cmd_learn(event, [], group_id)
        yield event.plain_result(result)

    @filter.command("skill_cancel", alias={"取消学习", "取消记录", "sc"})
    async def skill_cancel(self, event: AstrMessageEvent):
        """取消当前学习会话"""
        group_id = self._get_group_id(event)
        result = await self.cmd.cmd_cancel(event, group_id)
        yield event.plain_result(result)

    @filter.command("skill_status", alias={"学习状态", "st"})
    async def skill_status(self, event: AstrMessageEvent):
        """查看当前学习状态"""
        user_id = event.get_sender_id()
        group_id = self._get_group_id(event)
        session = self.storage.get_active_session(user_id, group_id)
        result = await self.cmd.cmd_status(event, session)
        yield event.plain_result(result)

    @filter.command("skill_save", alias={"保存技能", "ss"})
    async def skill_save(self, event: AstrMessageEvent):
        """保存学习内容为 Skill（需要指定名称）"""
        message_str = event.message_str.strip()
        parts = message_str.split(maxsplit=1)
        name = parts[1].strip() if len(parts) > 1 else None

        user_id = event.get_sender_id()
        group_id = self._get_group_id(event)
        session = self.storage.get_active_session(user_id, group_id)

        if not session or session.state != LearningState.LISTENING.value:
            yield event.plain_result(
                "📭 当前没有进行中的学习会话。\n"
                "发送 `/skill_learn` 或说「学习一下」开始学习吧~"
            )
            return

        if not session.messages:
            yield event.plain_result(
                "📝 学习会话中还没有内容呢。\n"
                "请发送一些你想让我学习的内容后再保存~"
            )
            return

        # 如果没有提供名称，主动引导
        if not name and not session.proposed_name:
            yield event.plain_result(
                "🤔 请为这个 Skill 取个名字吧~\n"
                "例如：`/skill_save 周报模板` 或 `/skill_save python-exception`\n"
                "\n💡 如果不确定，也可以直接发送 `/skill_save`，我会根据内容自动生成一个名字。"
            )
            # 允许空名称保存：进入 CONFIRMING，后续由 AI 命名

        # 标记为确认中
        session.state = LearningState.CONFIRMING.value
        if name:
            session.proposed_name = name
        self.storage.update_session(session)

        yield event.plain_result(
            f"🧠 正在调用 AI 分析你刚才教的 {len(session.messages)} 条内容，"
            f"大约需要 10-30 秒，请稍等..."
        )

        # 调用 LLM 生成 Skill
        try:
            skill = await self._generate_skill(event, session)
            if skill:
                # 检查是否首次保存
                existing_count = len(self.storage.list_skills())
                is_first = existing_count == 0

                # 保存到插件目录（备份）
                self.storage.save_skill(skill)
                # 根据配置自动部署到 AstrBot skills 目录
                deployed_path = None
                if self.auto_deploy:
                    deployed_path = self.storage.deploy_to_astrbot(skill)
                self.storage.end_session(user_id, group_id)

                if is_first:
                    msg = (
                        f"🎉 **恭喜！你创建了第一个 Skill！**\n"
                        f"\n名称: {skill.display_name or skill.name}"
                        f"\n类型: {skill.skill_type}"
                        f"\n描述: {skill.description}"
                    )
                else:
                    msg = (
                        f"✅ Skill 已保存！"
                        f"\n名称: {skill.display_name or skill.name}"
                        f"\n类型: {skill.skill_type}"
                        f"\n描述: {skill.description}"
                    )

                if self.auto_deploy:
                    if deployed_path:
                        msg += (
                            f"\n\n🚀 已自动部署到 AstrBot，"
                            f"现在可以在 Agent 中直接使用了！"
                        )
                    else:
                        msg += (
                            f"\n\n⚠️ 已保存到插件目录，但自动部署失败"
                            f"（可能无写入权限）。"
                        )

                msg += (
                    f"\n\n💡 试试对我说「使用 {skill.display_name or skill.name}」"
                    f"来测试效果，或发送 `/skill_view {skill.name}` 查看完整内容。"
                )
                yield event.plain_result(msg)
            else:
                yield event.plain_result(
                    "⚠️ 生成 Skill 失败了...\n"
                    "可能是 AI 服务暂时不可用，请稍后再试。"
                )
        except Exception as e:
            logger.error(f"[SkillLearner] 生成 Skill 失败: {e}")
            yield event.plain_result(
                "😵 生成 Skill 时遇到了一点问题...\n"
                "请检查网络连接后重试，或联系管理员查看日志。"
            )

    @filter.command("skill_list", alias={"技能列表", "skill列表", "skills"})
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
            yield event.plain_result(
                "❓ 你想查看哪个 Skill 呢？\n"
                "发送 `/skill_list` 可以看到所有已保存的 Skill 名称。\n"
                "然后发送 `/skill_view <名称>` 查看详情~"
            )
            return

        result = await self.cmd.cmd_view(event, parts[1].strip())
        yield event.plain_result(result)

    @filter.command("skill_delete")
    async def skill_delete(self, event: AstrMessageEvent):
        """删除指定 Skill（仅管理员可用）"""
        if not self._is_admin(event):
            yield event.plain_result(
                "🔒 只有群管理员可以删除 Skill 哦~\n"
                "如果你不是管理员，可以请管理员帮忙删除。"
            )
            return

        message_str = event.message_str.strip()
        parts = message_str.split(maxsplit=1)

        if len(parts) < 2:
            yield event.plain_result(
                "❓ 你想删除哪个 Skill 呢？\n"
                "发送 `/skill_list` 查看所有 Skill，\n"
                "然后发送 `/skill_delete <名称>` 删除~"
            )
            return

        result = await self.cmd.cmd_delete(event, parts[1].strip())
        yield event.plain_result(result)

    @filter.command("skill_export")
    async def skill_export(self, event: AstrMessageEvent):
        """导出 Skill 为 zip（AstrBot 兼容格式）"""
        message_str = event.message_str.strip()
        parts = message_str.split(maxsplit=1)

        if len(parts) < 2:
            yield event.plain_result(
                "❓ 你想导出哪个 Skill 呢？\n"
                "发送 `/skill_list` 查看所有 Skill，\n"
                "然后发送 `/skill_export <名称>` 导出~"
            )
            return

        result = await self.cmd.cmd_export(event, parts[1].strip())
        yield event.plain_result(result)

    @filter.command("skill_help", alias={"技能帮助", "skill帮助", "sh"})
    async def skill_help(self, event: AstrMessageEvent):
        """显示 Skill Learner 帮助信息"""
        user_id = event.get_sender_id()
        group_id = self._get_group_id(event)
        session = self.storage.get_active_session(user_id, group_id)
        in_learning = bool(session and session.state == LearningState.LISTENING.value)
        result = await self.cmd.cmd_help(event, in_learning=in_learning)
        yield event.plain_result(result)

    # ============================================================
    # 消息监听（自动触发学习模式）
    # ============================================================

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message_listener(self, event: AstrMessageEvent):
        """监听消息，检测自动触发关键词，记录学习会话内容"""
        user_id = event.get_sender_id()
        group_id = event.get_group_id() if hasattr(event, "get_group_id") else ""
        msg_text = event.message_str or ""

        if not msg_text:
            return

        # 忽略本插件的命令消息
        if msg_text.startswith("/skill_"):
            return

        # 群聊隔离：使用 group_id 维度隔离会话
        session = self.storage.get_active_session(user_id, group_id)

        # 检查是否在学习模式中
        if session and session.state == LearningState.LISTENING.value:
            session.messages.append({
                "role": "user",
                "content": msg_text,
            })
            session.group_id = group_id
            self.storage.update_session(session)

            count = len(session.messages)

            # 聚合回复：只在关键节点发送提示，避免刷屏
            AGGREGATE_POINTS = {1, 3, 5, 10, 15}
            if count in AGGREGATE_POINTS:
                encouragements = {
                    1: "📝 开始记录了！继续发送你想教我的内容~",
                    3: "📝 已经记录了 3 条内容，看起来很有意思！",
                    5: f"📝 {count} 条了，内容越来越丰富~",
                    10: f"📊 已记录 {count} 条！学得非常认真呢！",
                    15: f"📊 {count} 条！快要到上限了，准备保存吧~",
                }
                msg = encouragements.get(count, f"已记录 {count}/{self.cfg.max_learning_turns}")
                msg += f"\n💡 发送 `/skill_save <名称>` 保存 | `/skill_cancel` 取消"
                yield event.plain_result(msg)

            # 检查是否超过最大轮数
            if count >= self.cfg.max_learning_turns:
                yield event.plain_result(
                    f"📌 学习会话已达到最大消息数（{self.cfg.max_learning_turns}）。\n"
                    f"请发送 `/skill_save <名称>` 保存，或 `/skill_cancel` 取消。"
                )
            return

        # 检查自动触发关键词
        if self.cfg.enable_auto_learn:
            if self.learner.check_auto_trigger(msg_text, self.cfg.auto_trigger_keywords):
                session = self.storage.create_session(user_id, group_id)
                yield event.plain_result(
                    f"📖 检测到学习意图，已进入学习模式！（会话: {session.session_id}）\n"
                    f"请发送你想要我学习的内容~\n"
                    f"✅ 完成后发送 `/skill_save <名称>` 保存\n"
                    f"❌ 发送 `/skill_cancel` 取消"
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
