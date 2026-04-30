"""
存储层：管理学习会话和已保存的 Skills
使用 JSON 文件 + 文件系统存储 Skill 内容
"""

import json
import shutil
import zipfile
from pathlib import Path
from typing import Dict, List, Optional

from astrbot.api import logger
from astrbot.core.utils.astrbot_path import get_astrbot_skills_path

from .models import LearnedSkill, LearningSession


class SkillStorage:
    """Skill 存储管理器"""
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # 学习会话存储
        self.sessions_dir = self.data_dir / "sessions"
        self.sessions_dir.mkdir(exist_ok=True)
        
        # Skill 存储
        self.skills_dir = self.data_dir / "skills"
        self.skills_dir.mkdir(exist_ok=True)
        
        # 活跃会话缓存（内存中）
        self._active_sessions: Dict[str, LearningSession] = {}
        
        logger.info(f"[SkillLearner] 存储初始化完成: {self.data_dir}")
    
    # ========== 学习会话 ==========
    
    def create_session(self, user_id: str) -> LearningSession:
        """创建新的学习会话"""
        session = LearningSession(user_id=user_id, state="listening")
        self._active_sessions[user_id] = session
        self._save_session(session)
        logger.info(f"[SkillLearner] 创建学习会话: {session.session_id} (用户: {user_id})")
        return session
    
    def get_active_session(self, user_id: str) -> Optional[LearningSession]:
        """获取用户当前活跃的学习会话"""
        return self._active_sessions.get(user_id)
    
    def update_session(self, session: LearningSession):
        """更新学习会话"""
        self._active_sessions[session.user_id] = session
        self._save_session(session)
    
    def end_session(self, user_id: str):
        """结束学习会话"""
        if user_id in self._active_sessions:
            session = self._active_sessions[user_id]
            session.state = "idle"
            self._save_session(session)
            del self._active_sessions[user_id]
            logger.info(f"[SkillLearner] 结束学习会话: {session.session_id}")
    
    def _save_session(self, session: LearningSession):
        """持久化学习会话"""
        path = self.sessions_dir / f"{session.session_id}.json"
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(session.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"[SkillLearner] 保存会话失败: {e}")
    
    def _load_session(self, session_id: str) -> Optional[LearningSession]:
        """加载学习会话"""
        path = self.sessions_dir / f"{session_id}.json"
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return LearningSession.from_dict(json.load(f))
            except Exception as e:
                logger.warning(f"[SkillLearner] 加载会话失败: {e}")
        return None
    
    # ========== Skill 管理 ==========
    
    def save_skill(self, skill: LearnedSkill) -> Path:
        """保存 Skill 到文件系统"""
        # 创建 skill 目录
        skill_dir = self.skills_dir / skill.name
        skill_dir.mkdir(parents=True, exist_ok=True)
        
        # 写入 SKILL.md
        skill_md_path = skill_dir / "SKILL.md"
        with open(skill_md_path, "w", encoding="utf-8") as f:
            f.write(skill.skill_md_content)
        
        # 写入额外文件
        for filename, content in skill.additional_files.items():
            file_path = skill_dir / filename
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
        
        # 保存元数据
        meta_path = skill_dir / ".skill_meta.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(skill.to_dict(), f, ensure_ascii=False, indent=2)
        
        logger.info(f"[SkillLearner] Skill 已保存: {skill.name} -> {skill_dir}")
        return skill_dir
    
    def get_skill(self, name: str) -> Optional[LearnedSkill]:
        """获取指定 Skill"""
        skill_dir = self.skills_dir / name
        if not skill_dir.exists():
            return None
        
        meta_path = skill_dir / ".skill_meta.json"
        if meta_path.exists():
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    return LearnedSkill.from_dict(json.load(f))
            except Exception as e:
                logger.warning(f"[SkillLearner] 加载 Skill 元数据失败: {e}")
        return None
    
    def list_skills(self) -> List[LearnedSkill]:
        """列出所有已保存的 Skills"""
        skills = []
        if not self.skills_dir.exists():
            return skills
        
        for skill_dir in self.skills_dir.iterdir():
            if skill_dir.is_dir():
                skill = self.get_skill(skill_dir.name)
                if skill:
                    skills.append(skill)
        
        # 按创建时间倒序
        skills.sort(key=lambda s: s.created_at, reverse=True)
        return skills
    
    def delete_skill(self, name: str) -> bool:
        """删除 Skill"""
        skill_dir = self.skills_dir / name
        if skill_dir.exists():
            try:
                shutil.rmtree(skill_dir)
                logger.info(f"[SkillLearner] Skill 已删除: {name}")
                return True
            except Exception as e:
                logger.warning(f"[SkillLearner] 删除 Skill 失败: {e}")
        return False
    
    def get_skill_md(self, name: str) -> Optional[str]:
        """获取 Skill 的 SKILL.md 内容"""
        skill_md_path = self.skills_dir / name / "SKILL.md"
        if skill_md_path.exists():
            try:
                with open(skill_md_path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception as e:
                logger.warning(f"[SkillLearner] 读取 SKILL.md 失败: {e}")
        return None
    
    def export_skill_zip(self, name: str, output_dir: Path) -> Optional[Path]:
        """导出 Skill 为 zip 包（AstrBot 兼容格式）"""
        skill_dir = self.skills_dir / name
        if not skill_dir.exists():
            return None
        
        output_dir.mkdir(parents=True, exist_ok=True)
        zip_path = output_dir / f"{name}.zip"
        
        try:
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for file_path in skill_dir.iterdir():
                    if file_path.is_file():
                        zf.write(file_path, arcname=file_path.name)
            logger.info(f"[SkillLearner] Skill 已导出: {zip_path}")
            return zip_path
        except Exception as e:
            logger.warning(f"[SkillLearner] 导出 Skill 失败: {e}")
            return None
    
    def get_skill_dir(self, name: str) -> Optional[Path]:
        """获取 Skill 目录路径"""
        skill_dir = self.skills_dir / name
        if skill_dir.exists():
            return skill_dir
        return None
    
    # ========== AstrBot 自动部署 ==========
    
    def deploy_to_astrbot(self, skill: LearnedSkill) -> Optional[Path]:
        """将 Skill 自动部署到 AstrBot 的 skills 目录，使其立即可用"""
        try:
            astrbot_skills_dir = Path(get_astrbot_skills_path())
            astrbot_skills_dir.mkdir(parents=True, exist_ok=True)
            
            # 创建 skill 目录
            target_dir = astrbot_skills_dir / skill.name
            target_dir.mkdir(parents=True, exist_ok=True)
            
            # 写入 SKILL.md
            skill_md_path = target_dir / "SKILL.md"
            with open(skill_md_path, "w", encoding="utf-8") as f:
                f.write(skill.skill_md_content)
            
            # 写入额外文件
            for filename, content in skill.additional_files.items():
                file_path = target_dir / filename
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)
            
            logger.info(f"[SkillLearner] Skill 已自动部署到 AstrBot: {target_dir}")
            return target_dir
        except Exception as e:
            logger.error(f"[SkillLearner] 自动部署到 AstrBot 失败: {e}")
            return None
    
    def undeploy_from_astrbot(self, name: str) -> bool:
        """从 AstrBot skills 目录删除 Skill"""
        try:
            target_dir = Path(get_astrbot_skills_path()) / name
            if target_dir.exists():
                shutil.rmtree(target_dir)
                logger.info(f"[SkillLearner] Skill 已从 AstrBot 移除: {name}")
                return True
        except Exception as e:
            logger.error(f"[SkillLearner] 从 AstrBot 移除 Skill 失败: {e}")
        return False
