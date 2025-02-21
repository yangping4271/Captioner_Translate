from typing import Dict, Optional
from pathlib import Path
from openai import OpenAI
from .prompts import SUMMARIZER_PROMPT
from .config import SubtitleConfig
from utils.json_repair import parse_llm_response
from utils.logger import setup_logger

logger = setup_logger("subtitle_summarizer")


class SubtitleSummarizer:
    def __init__(
        self,
        config: Optional[SubtitleConfig] = None
    ):
        self.config = config or SubtitleConfig()
        self.client = OpenAI(
            base_url=self.config.openai_base_url,
            api_key=self.config.openai_api_key
        )

    def summarize(self, subtitle_content: str, input_file: str) -> Dict:
        """
        总结字幕内容
        Args:
            subtitle_content: 字幕内容
            input_file: 输入的字幕文件路径
        Returns:
            Dict: 包含总结信息的字典
        """
        try:
            # 使用pathlib处理文件名
            path = Path(input_file)
            # 获取不带扩展名的文件名
            readable_name = path.stem.replace('_', ' ').replace('-', ' ')

            logger.info(f"可读性文件名: {readable_name}")
            
            # 添加文件名上下文到字幕内容
            content_with_context = (
                f"The subtitle filename '{readable_name}' indicates this content is about {readable_name}. "
                f"Please keep this context in mind while summarizing the following subtitles:\n\n"
                f"{subtitle_content}"
            )
            
            message = [
                {"role": "system", "content": SUMMARIZER_PROMPT},
                {"role": "user", "content": content_with_context}
            ]
            
            response = self.client.chat.completions.create(
                model=self.config.llm_model,
                messages=message,
                temperature=0.7
            )
            
            summary = response.choices[0].message.content
            # 返回处理后的信息，包括可读文件名
            return {
                "summary": summary,
                "readable_name": readable_name
            }
            
        except Exception as e:
            logger.error(f"总结字幕失败: {e}")
            return {
                "summary": "",
                "readable_name": ""
            }
