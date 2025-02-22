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
    temperature: float = 0.7
    
    # 字幕分段配置
    max_word_count_english: int = 18
    segment_threshold: int = 500  # 每个分段的最大字数
    split_range: int = 30  # 在分割点前后寻找最大时间间隔的范围
    max_gap: int = 1500  # 允许每个词语之间的最大时间间隔 ms
    
    # 对齐配置
    similarity_threshold: float = 0.4
    minimum_alignment_ratio: float = 0.6
    
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