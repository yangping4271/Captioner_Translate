import os
from dataclasses import dataclass
from typing import Optional

@dataclass
class SubtitleConfig:
    """字幕处理配置类"""
    # API配置
    openai_base_url: str = os.getenv('OPENAI_BASE_URL', '')
    openai_api_key: str = os.getenv('OPENAI_API_KEY', '')
    llm_model: str = os.getenv('LLM_MODEL', 'gpt-4o-mini')
    
    # 处理配置
    target_language: str = "简体中文"
    thread_num: int = 18
    batch_size: int = 20
    
    # 功能开关
    need_reflect: bool = False
    
    def __post_init__(self):
        """验证配置"""
        if not self.openai_base_url or not self.openai_api_key:
            raise ValueError("环境变量 OPENAI_BASE_URL 和 OPENAI_API_KEY 必须设置")

# 文件相关常量
SRT_SUFFIX = ".srt"
OUTPUT_SUFFIX = "_zh.srt"
EN_OUTPUT_SUFFIX = "_en.srt"

# 延迟创建默认配置实例
def get_default_config() -> SubtitleConfig:
    """获取默认配置实例"""
    return SubtitleConfig() 