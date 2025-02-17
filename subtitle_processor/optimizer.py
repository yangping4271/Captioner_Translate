import difflib
import logging
import os
from concurrent.futures import ThreadPoolExecutor
import re
from typing import Dict
import concurrent.futures

import retry
from openai import OpenAI

from .subtitle_config import (
    TRANSLATE_PROMPT,
    REFLECT_TRANSLATE_PROMPT,
    SINGLE_TRANSLATE_PROMPT
)
from subtitle_processor.aligner import SubtitleAligner
from utils import json_repair
from utils.logger import setup_logger

logger = setup_logger("subtitle_optimizer")

BATCH_SIZE = 20
MAX_THREADS = 10
DEFAULT_MODEL = "gpt-4o-mini"


class SubtitleOptimizer:
    """A class for optimize and translating subtitles using OpenAI's API."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        summary_content: str = "",
        thread_num: int = MAX_THREADS,
        batch_num: int = BATCH_SIZE,
        target_language: str = "简体中文",
        llm_result_logger: logging.Logger = logger,
        need_remove_punctuation: bool = True,
        cjk_only: bool = True,
        reflect: bool = False
    ) -> None:
        base_url = os.getenv('OPENAI_BASE_URL')
        api_key = os.getenv('OPENAI_API_KEY')
        assert base_url and api_key, "环境变量 OPENAI_BASE_URL 和 OPENAI_API_KEY 必须设置"

        self.model = model
        self.client = OpenAI(base_url=base_url, api_key=api_key)

        self.summary_content = summary_content
        self.prompt = TRANSLATE_PROMPT
        self.target_language = target_language
        self.batch_num = batch_num
        self.thread_num = thread_num
        self.executor = ThreadPoolExecutor(max_workers=thread_num)  # 创建类级别的线程池
        self.llm_result_logger = llm_result_logger
        self.need_remove_punctuation = need_remove_punctuation
        self.cjk_only = cjk_only
        self.reflect = reflect
        
        # 注册退出处理
        import atexit
        atexit.register(self.stop)

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

    def translate_multi_thread(self, subtitle_json: Dict[int, str],
                               reflect: bool = False):
        batch_num = self.batch_num
        items = list(subtitle_json.items())[:]
        chunks = [dict(items[i:i + batch_num]) for i in range(0, len(items), batch_num)]

        def process_chunk(chunk):
            try:
                result = self.translate(chunk, reflect)
            except Exception as e:
                logger.error(f"翻译失败，使用单条翻译：{e}")
                single_result = self.translate_single(chunk)
                # 将单条翻译结果转换为新格式
                return {
                    "optimized_subtitles": chunk,  # 单条翻译不做优化，直接使用原文
                    "translated_subtitles": single_result
                }
            return result

        results = list(self.executor.map(process_chunk, chunks))

        # 合并所有结果
        optimized_subtitles = {}
        translated_subtitles = {}
        for result in results:
            optimized_subtitles.update(result["optimized_subtitles"])
            translated_subtitles.update(result["translated_subtitles"])
        
        return {
            "optimized_subtitles": optimized_subtitles,
            "translated_subtitles": translated_subtitles
        }
    
    @retry.retry(tries=2)
    def translate(self, original_subtitle: Dict[int, str], reflect=False) -> Dict[int, str]:
        """优化并翻译给定的字幕。"""
        if reflect:
            return self._reflect_translate(original_subtitle)
        else:
            return self._normal_translate(original_subtitle)

    def _reflect_translate(self, original_subtitle: Dict[int, str]):
        logger.info(f"[+]正在反思翻译字幕：{next(iter(original_subtitle))} - {next(reversed(original_subtitle))}")
        message = self._create_translate_message(original_subtitle, reflect=True)
        response = self.client.chat.completions.create(
            model=self.model,
            stream=False,
            messages=message,
            temperature=0.7)
        response_content = json_repair.loads(response.choices[0].message.content)
        # print(response_content)
        optimized_text = {k: v["optimized_subtitle"] for k, v in response_content.items()}  # 字幕文本
        aligned_subtitle = repair_subtitle(original_subtitle, optimized_text)  # 修复字幕对齐问题
        # 在 translations 中查找对应的翻译  文本-翻译 映射
        translations = {item["optimized_subtitle"]: item["revised_translation"] for item in response_content.values()}
        
        translated_subtitle = {}
        for k, v in aligned_subtitle.items():
            original_text = self.remove_punctuation(v)
            translated_text = self.remove_punctuation(translations.get(v, ' '))
            translated_subtitle[k] = f"{original_text}\n{translated_text}"

        if self.llm_result_logger:
            for k, v in response_content.items():
                if original_subtitle[k] != v['optimized_subtitle']  :
                    self.llm_result_logger.info("==============优化字幕=========================")
                    self.llm_result_logger.info(f"原始字幕：{original_subtitle[k]}")
                    self.llm_result_logger.info(f"优化字幕：{v['optimized_subtitle']}")
                if v['translation'] != v['revised_translation']:
                    self.llm_result_logger.info("==============反思翻译=========================")
                    self.llm_result_logger.info(f"反思建议：{v['revise_suggestions']}")
                    self.llm_result_logger.info(f"翻译后字幕：{v['translation']}")
                    self.llm_result_logger.info(f"反思后字幕：{v['revised_translation']}")
        
        # 返回优化后的字幕和翻译结果
        return {
            "optimized_subtitles": aligned_subtitle,
            "translated_subtitles": translated_subtitle
        }

    def _normal_translate(self, original_subtitle: Dict[int, str]):
        logger.info(f"[+]正在翻译字幕：{next(iter(original_subtitle))} - {next(reversed(original_subtitle))}")
        # 让大模型直接处理校正和翻译，不需要预处理
        message = self._create_translate_message(original_subtitle)
        logger.debug(f"message: {message}")
        response = self.client.chat.completions.create(
            model=self.model,
            stream=False,
            messages=message,
            temperature=0.7)
        response_content = json_repair.loads(response.choices[0].message.content)
        if len(response_content) != len(original_subtitle):
            logger.info("===========翻译结果数量不一致===========")
            logger.info(f"原始字幕: {original_subtitle}")
            logger.info(f"字幕数量: {len(original_subtitle)}")
            logger.info(f"翻译结果: {response_content}")
            logger.info(f"翻译结果数量: {len(response_content)}")
            
        assert isinstance(response_content, dict) and len(response_content) == len(original_subtitle), "翻译结果错误"
        
        # 提取优化后的字幕和翻译
        optimized_text = {k: v["optimized_subtitle"] for k, v in response_content.items()}
        aligned_subtitle = repair_subtitle(original_subtitle, optimized_text)  # 修复字幕对齐问题
        
        # 在 translations 中查找对应的翻译
        translations = {item["optimized_subtitle"]: item["translation"] for item in response_content.values()}
        
        translated_subtitle = {}
        for k, v in aligned_subtitle.items():
            original_text = self.remove_punctuation(v)
            translated_text = self.remove_punctuation(translations.get(v, ' '))
            translated_subtitle[k] = f"{original_text}\n{translated_text}"

        if self.llm_result_logger:
            for k, v in response_content.items():
                if original_subtitle[k] != v['optimized_subtitle']:
                    self.llm_result_logger.info("==============优化字幕=========================")
                    self.llm_result_logger.info(f"原始字幕：{original_subtitle[k]}")
                    self.llm_result_logger.info(f"优化字幕：{v['optimized_subtitle']}")

        # 返回优化后的字幕和翻译结果
        return {
            "optimized_subtitles": aligned_subtitle,
            "translated_subtitles": translated_subtitle
        }

    def _create_translate_message(self, original_subtitle: Dict[int, str], reflect=False):
        input_content = f"correct the original subtitles, and translate them into {self.target_language}:\n<input_subtitle>{str(original_subtitle)}</input_subtitle>"
        if self.summary_content:
            input_content += f"\nThe following is reference material related to subtitles, based on which the subtitles will be corrected, optimized, and translated. Pay special attention to the potential misrecognitions and use them along with context to make intelligent corrections:\n<prompt>{self.summary_content}</prompt>\n"
        if reflect:
            prompt = REFLECT_TRANSLATE_PROMPT.replace("[TargetLanguage]", self.target_language)
        else:
            prompt = TRANSLATE_PROMPT.replace("[TargetLanguage]", self.target_language)
        message = [{"role": "system", "content": prompt},
                   {"role": "user", "content": input_content}]
        return message

    def translate_single(self, original_subtitle: Dict[int, str]) -> Dict[int, str]:
        """单条字幕翻译，用于在批量翻译失败时的备选方案"""
        translated_subtitle = {}
        for key, value in original_subtitle.items():
            try:
                message = [{"role": "system",
                            "content": SINGLE_TRANSLATE_PROMPT.replace("[TargetLanguage]", self.target_language)},
                           {"role": "user", "content": value}]
                response = self.client.chat.completions.create(
                    model=self.model,
                    stream=False,
                    messages=message)
                translate = response.choices[0].message.content.replace("\n", "")
                original_text = self.remove_punctuation(value)
                translated_text = self.remove_punctuation(translate)
                translated_subtitle[key] = f"{original_text}\n{translated_text}"
                logger.info(f"单条翻译结果: {translated_subtitle[key]}")
            except Exception as e:
                logger.error(f"单条翻译失败: {e}")
                translated_subtitle[key] = f"{value}\n "
        
        # 单条翻译不做优化，直接返回原文作为优化后的字幕
        return {
            "optimized_subtitles": original_subtitle,
            "translated_subtitles": translated_subtitle
        }

    def remove_punctuation(self, text: str) -> str:
        """
        移除字幕中的标点符号
        """
        cjk_only = self.cjk_only
        need_remove_punctuation = self.need_remove_punctuation
        def is_mainly_cjk(text: str) -> bool:
            """
            判断文本是否主要由中日韩文字组成
            """
            # 定义CJK字符的Unicode范围
            cjk_patterns = [
                r'[\u4e00-\u9fff]',           # 中日韩统一表意文字
                r'[\u3040-\u309f]',           # 平假名
                r'[\u30a0-\u30ff]',           # 片假名
                r'[\uac00-\ud7af]',           # 韩文音节
            ]
            cjk_count = 0
            for pattern in cjk_patterns:
                cjk_count += len(re.findall(pattern, text))
            total_chars = len(''.join(text.split()))
            return cjk_count / total_chars > 0.4 if total_chars > 0 else False

        punctuation = r'[,.!?;:，。！？；：、]'
        if not need_remove_punctuation or (cjk_only and not is_mainly_cjk(text)):
            return text
        # 移除末尾标点符号
        return re.sub(f'{punctuation}+$', '', text.strip())


def repair_subtitle(dict1, dict2) -> Dict[int, str]:
    list1 = list(dict1.values())
    list2 = list(dict2.values())
    text_aligner = SubtitleAligner()
    aligned_source, aligned_target = text_aligner.align_texts(list1, list2)

    assert len(aligned_source) == len(aligned_target), "对齐后字幕长度不一致"
    # 验证是否匹配
    similar_list = calculate_similarity_list(aligned_source, aligned_target)
    if similar_list.count(True) / len(similar_list) >= 0.89:
        # logger.info(f"修复成功！序列匹配相似度：{similar_list.count(True) / len(similar_list):.2f}")
        start_id = next(iter(dict1.keys()))
        modify_dict = {str(int(start_id) + i): value for i, value in enumerate(aligned_target)}
        return modify_dict
    else:
        logger.error(f"修复失败！相似度：{similar_list.count(True) / len(similar_list):.2f}")
        logger.error(f"源字幕：{list1}")
        logger.error(f"目标字幕：{list2}")
        raise ValueError("Fail to repair.")


def is_similar(text1, text2, threshold=0.4):
    similarity = difflib.SequenceMatcher(None, text1, text2).ratio()
    return similarity >= threshold


def calculate_similarity_list(list1, list2, threshold=0.5):
    max_len = min(len(list1), len(list2))
    similar_list = [False] * max_len  # 初始化相似性列表

    for i in range(max_len):
        similar_list[i] = is_similar(list1[i], list2[i], threshold)

    return similar_list


if __name__ == "__main__":
    # os.environ['OPENAI_BASE_URL'] = 'https://api.gptgod.online/v1'
    # os.environ['OPENAI_API_KEY'] = 'sk-4StuHHm6Z1q0VcPHdPTUBdmKMsHW9JNZKe4jV7pJikBsGRuj'
    # MODEL = "gpt-4o-mini"
    os.environ['OPENAI_BASE_URL'] = 'https://api.turboai.one/v1'
    os.environ['OPENAI_API_KEY'] = 'sk-ZOCYCz5kexAS3X8JD3A33a5eB20f486eA26896798055F2C5'
    MODEL = "gpt-4o-mini"
