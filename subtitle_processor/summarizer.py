from typing import Dict, Optional
from openai import OpenAI
from .prompts import SUMMARIZER_PROMPT
from .config import SubtitleConfig
from utils import json_repair
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

    def summarize(self, subtitle_content: str) -> Dict:
        """
        总结字幕内容
        """
        logger.info("开始摘要化字幕内容")
        message = [
            {"role": "system", "content": SUMMARIZER_PROMPT},
            {"role": "user", "content": subtitle_content}
        ]
        response = self.client.chat.completions.create(
            model=self.config.llm_model,
            stream=False,
            messages=message
        )
        result = json_repair.loads(response.choices[0].message.content)
        return result
