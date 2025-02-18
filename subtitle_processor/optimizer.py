import difflib
import logging
import os
from concurrent.futures import ThreadPoolExecutor
import re
from typing import Dict, Optional, List
import concurrent.futures
import json

import retry
from openai import OpenAI

from .prompts import (
    TRANSLATE_PROMPT,
    REFLECT_TRANSLATE_PROMPT,
    SINGLE_TRANSLATE_PROMPT
)
from .config import SubtitleConfig
from subtitle_processor.aligner import SubtitleAligner
from utils import json_repair
from utils.logger import setup_logger

logger = setup_logger("subtitle_optimizer")

BATCH_SIZE = 20
MAX_THREADS = 10
DEFAULT_MODEL = "gpt-3.5-turbo"


class SubtitleOptimizer:
    """A class for optimize and translating subtitles using OpenAI's API."""

    def __init__(
        self,
        config: Optional[SubtitleConfig] = None,
        need_reflect: bool = False
    ):
        self.config = config or SubtitleConfig()
        self.need_reflect = need_reflect
        self.client = OpenAI(
            base_url=self.config.openai_base_url,
            api_key=self.config.openai_api_key
        )
        self.thread_num = self.config.thread_num
        self.batch_num = self.config.batch_size

    def translate(self, asr_data, summary_content: Dict) -> List[Dict]:
        """
        翻译字幕
        """
        subtitle_json = {str(k): v["original_subtitle"] 
                        for k, v in asr_data.to_json().items()}
        if self.need_reflect:
            return self._reflect_translate(subtitle_json, summary_content)
        else:
            return self._translate(subtitle_json, summary_content)

    def stop(self):
        """优雅关闭线程池"""
        if hasattr(self, 'executor'):
            try:
                logger.info("正在等待线程池任务完成...")
                self.executor.shutdown(wait=True)
                logger.info("线程池已关闭")
            except Exception as e:
                logger.error(f"关闭线程池时发生错误: {e}")
            finally:
                self.executor = None

    def translate_multi_thread(self, subtitle_json: Dict[int, str], reflect: bool = False):
        """多线程批量翻译字幕"""
        if reflect:
            return self._batch_translate(subtitle_json, use_reflect=True)
        
        try:
            return self._batch_translate(subtitle_json, use_reflect=False)
        except Exception as e:
            logger.error(f"批量翻译失败，使用单条翻译：{e}")
            return self._translate_by_single(subtitle_json)

    def _batch_translate(self, subtitle_json: Dict[int, str], use_reflect: bool = False) -> Dict:
        """批量翻译字幕的核心方法"""
        items = list(subtitle_json.items())[:]
        chunks = [dict(items[i:i + self.batch_num]) 
                 for i in range(0, len(items), self.batch_num)]
        
        # 创建翻译任务
        futures = []
        for chunk in chunks:
            if use_reflect:
                future = self.executor.submit(self._reflect_translate, chunk)
            else:
                future = self.executor.submit(self._translate, chunk)
            futures.append(future)
        
        # 收集结果
        optimized_subtitles = {}
        translated_subtitles = {}
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
                optimized_subtitles.update(result["optimized_subtitles"])
                translated_subtitles.update(result["translated_subtitles"])
            except Exception as e:
                logger.error(f"批量翻译任务失败：{e}")
                raise
        
        return {
            "optimized_subtitles": optimized_subtitles,
            "translated_subtitles": {
                "translated_subtitles": translated_subtitles
            }
        }

    def _translate_by_single(self, subtitle_json: Dict[int, str]) -> Dict:
        """使用单条翻译模式处理字幕"""
        items = list(subtitle_json.items())[:]
        chunks = [dict(items[i:i + self.batch_num]) 
                 for i in range(0, len(items), self.batch_num)]
        
        # 创建翻译任务
        futures = []
        for chunk in chunks:
            future = self.executor.submit(self._translate_chunk_by_single, chunk)
            futures.append(future)
        
        # 收集结果
        optimized_subtitles = {}
        translated_subtitles = {}
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
                optimized_subtitles.update(result["optimized_subtitles"])
                translated_subtitles.update(result["translated_subtitles"])
            except Exception as e:
                logger.error(f"单条翻译任务失败：{e}")
                raise
        
        # 确保返回格式与批量翻译一致
        return {
            "optimized_subtitles": optimized_subtitles,
            "translated_subtitles": {
                "translated_subtitles": translated_subtitles
            }
        }

    @retry.retry(tries=2)
    def _translate_chunk_by_single(self, subtitle_chunk: Dict[int, str]) -> Dict:
        """单条翻译模式的核心方法"""
        translated_subtitle = {}
        message = [{"role": "system",
                   "content": SINGLE_TRANSLATE_PROMPT.replace("[TargetLanguage]", self.config.target_language)}]
        
        for key, value in subtitle_chunk.items():
            try:
                message.append({"role": "user", "content": value})
                response = self.client.chat.completions.create(
                    model=self.config.model,
                    stream=False,
                    messages=message)
                message.pop()
                
                translate = response.choices[0].message.content.strip()
                translated_subtitle[key] = translate
                logger.info(f"单条翻译原文: {value}")
                logger.info(f"单条翻译结果: {translate}")
            except Exception as e:
                logger.error(f"单条翻译失败: {e}")
                translated_subtitle[key] = ""
        
        return {
            "optimized_subtitles": subtitle_chunk,
            "translated_subtitles": translated_subtitle
        }

    def _create_translate_message(self, original_subtitle: Dict[str, str], summary_content: Dict, reflect=False):
        """创建翻译提示消息"""
        input_content = (f"correct the original subtitles, and translate them into {self.config.target_language}:"
                        f"\n<input_subtitle>{str(original_subtitle)}</input_subtitle>")

        if summary_content:
            input_content += (f"\nThe following is reference material related to subtitles, based on which "
                            f"the subtitles will be corrected, optimized, and translated. Pay special attention "
                            f"to the potential misrecognitions and use them along with context to make intelligent "
                            f"corrections:\n<prompt>{summary_content}</prompt>\n")

        prompt = REFLECT_TRANSLATE_PROMPT if reflect else TRANSLATE_PROMPT
        prompt = prompt.replace("[TargetLanguage]", self.config.target_language)

        return [
            {"role": "system", "content": prompt},
            {"role": "user", "content": input_content}
        ]

    def _reflect_translate(self, original_subtitle: Dict[str, str], summary_content: Dict) -> List[Dict]:
        """
        反思翻译字幕
        """
        subtitle_keys = sorted(map(int, original_subtitle.keys()))
        logger.info(f"[+]正在反思翻译字幕：{subtitle_keys[0]} - {subtitle_keys[-1]}")
        message = self._create_translate_message(original_subtitle, summary_content, reflect=True)
        response = self.client.chat.completions.create(
            model=self.config.llm_model,
            stream=False,
            messages=message,
            temperature=0.7
        )
        try:
            response_content = json.loads(response.choices[0].message.content)
        except json.JSONDecodeError:
            logger.error("解析JSON失败，尝试修复")
            content = response.choices[0].message.content
            response_content = json_repair.loads(content)

        translated_subtitle = []
        for k, v in response_content.items():
            k = int(k)  # 将字符串键转换为整数
            translated_text = {
                "id": k,
                "original": original_subtitle[str(k)],
                "optimized": v["optimized_subtitle"],
                "translation": v["translation"],
                "revised_translation": v["revised_translation"],
                "revise_suggestions": v["revise_suggestions"]
            }
            translated_subtitle.append(translated_text)

            # 记录优化和翻译的变化
            if translated_text["original"] != translated_text["optimized"]:
                logger.info("==============优化字幕=========================")
                logger.info(f"原始字幕：{translated_text['original']}")
                logger.info(f"优化字幕：{translated_text['optimized']}")
            if translated_text["translation"] != translated_text["revised_translation"]:
                logger.info("==============反思翻译=========================")
                logger.info(f"反思建议：{translated_text['revise_suggestions']}")
                logger.info(f"翻译后字幕：{translated_text['translation']}")
                logger.info(f"反思后字幕：{translated_text['revised_translation']}")

        return translated_subtitle

    def _translate(self, original_subtitle: Dict[str, str], summary_content: Dict) -> List[Dict]:
        """
        翻译字幕
        """
        subtitle_keys = sorted(map(int, original_subtitle.keys()))
        logger.info(f"[+]正在翻译字幕：{subtitle_keys[0]} - {subtitle_keys[-1]}")
        message = self._create_translate_message(original_subtitle, summary_content, reflect=False)
        response = self.client.chat.completions.create(
            model=self.config.llm_model,
            stream=False,
            messages=message,
            temperature=0.7
        )
        try:
            response_content = json.loads(response.choices[0].message.content)
        except json.JSONDecodeError:
            logger.error("解析JSON失败，尝试修复")
            content = response.choices[0].message.content
            response_content = json_repair.loads(content)

        translated_subtitle = []
        for k, v in response_content.items():
            k = int(k)  # 将字符串键转换为整数
            translated_text = {
                "id": k,
                "original": original_subtitle[str(k)],
                "optimized": v["optimized_subtitle"],
                "translation": v["translation"]
            }
            translated_subtitle.append(translated_text)

            # 记录优化的变化
            if translated_text["original"] != translated_text["optimized"]:
                logger.info("==============优化字幕=========================")
                logger.info(f"原始字幕：{translated_text['original']}")
                logger.info(f"优化字幕：{translated_text['optimized']}")

        return translated_subtitle


if __name__ == "__main__":
    os.environ['OPENAI_BASE_URL'] = 'https://api.turboai.one/v1'
    os.environ['OPENAI_API_KEY'] = 'sk-ZOCYCz5kexAS3X8JD3A33a5eB20f486eA26896798055F2C5'
    MODEL = "gpt-4o-mini"
