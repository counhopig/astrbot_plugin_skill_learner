"""
数据模型层：Skill 学习器的核心数据结构
"""

import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any


class LearningState(Enum):
    """学习会话状态"""
    IDLE = "idle"           # 空闲，未在学习
    LISTENING = "listening" # 正在监听用户输入
    CONFIRMING = "confirming" # 等待用户确认保存


class SkillType(Enum):
    """Skill 类型"""
    WORKFLOW = "workflow"     # 工作流型：一系列步骤
    KNOWLEDGE = "knowledge"   # 知识型：领域知识、规则
    TOOL = "tool"             # 工具型：可执行脚本/代码
    PROMPT = "prompt"         # 提示词型：可复用的 Prompt 模板


@dataclass
class LearningSession:
    """一次学习会话的上下文"""
    session_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    user_id: str = ""
    started_at: float = field(default_factory=time.time)
    messages: List[Dict[str, str]] = field(default_factory=list)
    summary: str = ""         # AI 生成的摘要
    proposed_name: str = ""   # AI 建议的 skill 名称
    proposed_type: str = ""   # AI 建议的 skill 类型
    state: str = LearningState.IDLE.value
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, d: dict) -> "LearningSession":
        return cls(**d)


@dataclass
class LearnedSkill:
    """一个已学习的 Skill"""
    skill_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""            # Skill 名称（英文标识，用于文件夹名）
    display_name: str = ""    # 展示名称（中文可读）
    skill_type: str = SkillType.WORKFLOW.value
    description: str = ""     # 描述
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    created_by: str = ""      # 创建者用户ID
    source_session: str = ""  # 来源学习会话ID
    tags: List[str] = field(default_factory=list)
    skill_md_content: str = ""  # SKILL.md 完整内容
    additional_files: Dict[str, str] = field(default_factory=dict)  # 额外文件 {filename: content}
    usage_count: int = 0      # 使用次数
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, d: dict) -> "LearnedSkill":
        return cls(**d)
    
    @property
    def created_at_str(self) -> str:
        return datetime.fromtimestamp(self.created_at).strftime("%Y-%m-%d %H:%M")


@dataclass
class LearningConfig:
    """学习配置"""
    auto_trigger_keywords: List[str] = field(default_factory=lambda: [
        "记住这个", "保存为skill", "学习一下", "记下来", 
        "记住", "保存技能", "学一下", "learn this"
    ])
    max_learning_turns: int = 20  # 一次学习会话最大轮数
    enable_auto_learn: bool = True  # 是否启用关键词自动触发
    enable_proactive_suggest: bool = True  # 是否主动建议保存高频操作
    proactive_threshold: int = 3  # 同一操作重复几次后主动建议
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, d: dict) -> "LearningConfig":
        return cls(**d)
