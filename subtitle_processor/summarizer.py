import os

from openai import OpenAI

from subtitle_processor.subtitle_config import SUMMARIZER_PROMPT
from utils import json_repair
from utils.logger import setup_logger

logger = setup_logger("subtitle_summarizer")


class SubtitleSummarizer:
    def __init__(self, model) -> None:
        base_url = os.getenv('OPENAI_BASE_URL')
        api_key = os.getenv('OPENAI_API_KEY')

        if not base_url or not api_key:
            raise ValueError("环境变量 OPENAI_BASE_URL 和 OPENAI_API_KEY 必须设置")

        self.model = model
        self.client = OpenAI(base_url=base_url, api_key=api_key)

    def summarize(self, subtitle_content: str) -> str:
        logger.info(f"开始摘要化字幕内容")
        try:
            # subtitle_content = subtitle_content[:3000]
            response = self.client.chat.completions.create(
                model=self.model,
                stream=False,
                messages=[
                    {"role": "system", "content": SUMMARIZER_PROMPT},
                    {"role": "user", "content": f"summarize the video content:\n{subtitle_content}"}
                ],
                temperature=0.5
            )
            return str(json_repair.loads(response.choices[0].message.content))
        except Exception as e:
            logger.exception(f"摘要化字幕内容失败: {e}")
            return ""
    
    

if __name__ == "__main__":
    summarizer = SubtitleSummarizer()
    example_subtitles = {0: '既然是想做并发编程', 1: '比如说肯定是想干嘛', 2: '开启多条线程来同时执行任务'}
    example_subtitles = dict(list(example_subtitles.items())[:5])

    content = "".join(example_subtitles.values())
    result = summarizer.summarize(content)
    print(result)
