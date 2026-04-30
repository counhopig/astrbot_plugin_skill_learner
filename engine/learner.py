"""
学习引擎：分析对话内容，提取可复用的知识或流程
"""

import json
from typing import Dict, List, Optional

from astrbot.api import logger

from ..models import LearningSession, SkillType


class LearningEngine:
    """负责分析学习会话，生成 Skill 摘要和建议"""
    
    def __init__(self):
        pass
    
    def build_analysis_prompt(self, session: LearningSession) -> str:
        """构建让 LLM 分析学习内容的 Prompt"""
        messages_text = self._format_messages(session.messages)
        
        prompt = f"""请分析以下用户教授的内容，并提取关键信息。

=== 对话内容 ===
{messages_text}

=== 任务 ===
1. 总结这段对话的核心内容（50字以内）
2. 判断内容类型：workflow（工作流/步骤）、knowledge（知识/规则）、tool（工具/脚本）、prompt（提示词模板）
3. 提出一个简短的英文 skill 名称（小写字母、数字、连字符，如：pdf-processing）
4. 提出一个中文展示名称
5. 列出 2-4 个标签

请用以下 JSON 格式输出（只输出 JSON，不要其他内容）：
```json
{{
  "summary": "核心内容摘要",
  "skill_type": "workflow|knowledge|tool|prompt",
  "proposed_name": "english-skill-name",
  "display_name": "中文名称",
  "tags": ["标签1", "标签2"],
  "description": "一句话描述这个 skill 的用途"
}}
```
"""
        return prompt
    
    def build_skill_generation_prompt(
        self, 
        session: LearningSession,
        skill_type: str,
        name: str,
        display_name: str,
        description: str,
        tags: List[str]
    ) -> str:
        """构建生成 SKILL.md 的 Prompt"""
        messages_text = self._format_messages(session.messages)
        
        tag_str = ", ".join(tags) if tags else ""
        
        prompt = f"""请根据以下用户教授的内容，生成一个符合 Anthropic Skills 规范的 SKILL.md 文件。

=== 内容类型 ===
{skill_type}

=== 对话内容 ===
{messages_text}

=== 要求 ===
- 生成的 SKILL.md 必须包含 YAML frontmatter
- frontmatter 必须包含：name、description
- 指令部分使用 Markdown 格式
- 内容要详细、具体、可操作
- 如果是工作流型，列出明确的步骤
- 如果是知识型，整理成清晰的条目
- 如果是工具型，提供完整的代码示例
- 如果是提示词型，提供可复用的模板

请直接输出 SKILL.md 的完整内容，不需要任何额外说明：

```markdown
---
name: {name}
description: {description}
version: "1.0.0"
metadata:
  tags: [{tag_str}]
  display_name: "{display_name}"
  source: "user-taught"
---

# {display_name}

{description}

## 内容

[根据对话内容整理的具体指令/知识/代码/模板]

## 示例

[提供 1-2 个使用示例]

## 注意事项

[列出常见陷阱或注意事项]
```
"""
        return prompt
    
    def parse_analysis_result(self, llm_text: str) -> Optional[Dict]:
        """解析 LLM 分析结果"""
        try:
            json_text = self._extract_json(llm_text)
            if json_text:
                return json.loads(json_text)
        except Exception as e:
            logger.warning(f"[SkillLearner] 解析分析结果失败: {e}")
        return None
    
    def parse_skill_md(self, llm_text: str) -> Optional[str]:
        """从 LLM 输出中提取 SKILL.md 内容"""
        if "---" in llm_text:
            start = llm_text.find("---")
            end = llm_text.rfind("```")
            if end > start:
                return llm_text[start:end].strip()
            return llm_text[start:].strip()
        return llm_text.strip()
    
    def _format_messages(self, messages: List[Dict[str, str]]) -> str:
        """格式化消息列表为文本"""
        lines = []
        for m in messages:
            role = m.get("role", "unknown")
            content = m.get("content", "")
            lines.append(f"{role}: {content}")
        return "\n".join(lines)
    
    def _extract_json(self, text: str) -> Optional[str]:
        """从文本中提取 JSON"""
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end > start:
                return text[start:end].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            if end > start:
                return text[start:end].strip()
        
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return text[start:end+1]
        
        return None
    
    def check_auto_trigger(self, text: str, keywords: List[str]) -> bool:
        """检查消息是否包含自动触发关键词"""
        text_lower = text.lower()
        for kw in keywords:
            if kw.lower() in text_lower:
                return True
        return False
