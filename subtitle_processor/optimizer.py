from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Optional, List
import concurrent.futures

import retry
from openai import OpenAI

from .prompts import (
    TRANSLATE_PROMPT,
    REFLECT_TRANSLATE_PROMPT,
    SINGLE_TRANSLATE_PROMPT
)
from .config import SubtitleConfig
from utils.json_repair import parse_llm_response
from utils.logger import setup_logger

logger = setup_logger("subtitle_optimizer")

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
        self.executor = ThreadPoolExecutor(max_workers=self.thread_num)
        # 改用字典存储日志，使用ID作为键以自动去重
        self.batch_logs = {}

    def translate(self, asr_data, summary_content: Dict) -> List[Dict]:
        """
        翻译字幕
        Args:
            asr_data: ASR识别结果
            summary_content: 总结内容，包含summary和readable_name
        Returns:
            List[Dict]: 翻译结果列表
        """
        try:
            # 清空之前的日志
            self.batch_logs.clear()
            
            subtitle_json = {str(k): v["original_subtitle"] 
                            for k, v in asr_data.to_json().items()}
            
            # 使用多线程批量翻译
            result = self.translate_multi_thread(subtitle_json, self.need_reflect, summary_content)
            
            # 转换结果格式
            translated_subtitle = []
            for k, v in result["optimized_subtitles"].items():
                translated_text = {
                    "id": int(k),
                    "original": subtitle_json[str(k)],
                    "optimized": v,
                    "translation": result["translated_subtitles"]["translated_subtitles"][k]
                }
                # 如果是反思模式，添加反思相关的字段
                if self.need_reflect and isinstance(result["translated_subtitles"]["translated_subtitles"][k], dict):
                    translated_text.update({
                        "revised_translation": result["translated_subtitles"]["translated_subtitles"][k].get("revised_translation"),
                        "revise_suggestions": result["translated_subtitles"]["translated_subtitles"][k].get("revise_suggestions"),
                        "translation": result["translated_subtitles"]["translated_subtitles"][k].get("translation")
                    })
                translated_subtitle.append(translated_text)
            
            # 所有批次处理完成后，统一输出日志
            self._print_all_batch_logs()
            return translated_subtitle
        finally:
            self.stop()  # 确保线程池被关闭

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

    def translate_multi_thread(self, subtitle_json: Dict[int, str], reflect: bool = False, 
                             summary_content: Dict = None):
        """多线程批量翻译字幕"""
        if reflect:
            return self._batch_translate(subtitle_json, use_reflect=True, summary_content=summary_content)
        
        try:
            return self._batch_translate(subtitle_json, use_reflect=False, summary_content=summary_content)
        except Exception as e:
            logger.error(f"批量翻译失败，使用单条翻译：{e}")
            return self._translate_by_single(subtitle_json)

    def _batch_translate(self, subtitle_json: Dict[int, str], use_reflect: bool = False, 
                         summary_content: Dict = None) -> Dict:
        """批量翻译字幕的核心方法"""
        items = list(subtitle_json.items())[:]
        chunks = [dict(items[i:i + self.batch_num]) 
                 for i in range(0, len(items), self.batch_num)]
        
        # 创建翻译任务
        futures = []
        for chunk in chunks:
            if use_reflect:
                future = self.executor.submit(self._reflect_translate, chunk, summary_content)
            else:
                future = self.executor.submit(self._translate, chunk, summary_content)
            futures.append(future)
        
        # 收集结果
        optimized_subtitles = {}
        translated_subtitles = {}
        total = len(futures)
        for i, future in enumerate(concurrent.futures.as_completed(futures), 1):
            try:
                result = future.result()
                for item in result:
                    k = str(item["id"])
                    optimized_subtitles[k] = item["optimized"]
                    # 保存完整的翻译信息
                    if "revised_translation" in item:
                        translated_subtitles[k] = {
                            "translation": item["translation"],
                            "revised_translation": item["revised_translation"],
                            "revise_suggestions": item["revise_suggestions"]
                        }
                    else:
                        translated_subtitles[k] = item["translation"]
                logger.info(f"批量翻译进度: {i}/{total} 批次")
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
        total = len(futures)
        for i, future in enumerate(concurrent.futures.as_completed(futures), 1):
            try:
                result = future.result()
                for k, v in result["optimized_subtitles"].items():
                    optimized_subtitles[str(k)] = v
                    translated_subtitles[str(k)] = result["translated_subtitles"][k]
                logger.info(f"单条翻译进度: {i}/{total} 批次")
            except Exception as e:
                logger.error(f"单条翻译任务失败：{e}")
                raise
        
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
                    model=self.config.llm_model,
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

    def _create_translate_message(self, original_subtitle: Dict[str, str], 
                                summary_content: Dict, reflect=False):
        """创建翻译提示消息"""
        input_content = (f"correct the original subtitles, and translate them into {self.config.target_language}:"
                        f"\n<input_subtitle>{str(original_subtitle)}</input_subtitle>")

        if summary_content:
            input_content += (f"\nThe following is reference material related to subtitles, based on which "
                            f"the subtitles will be corrected, optimized, and translated:"
                            f"\n<prompt>{summary_content.get('summary', '')}</prompt>\n")

        prompt = REFLECT_TRANSLATE_PROMPT if reflect else TRANSLATE_PROMPT
        prompt = prompt.replace("[TargetLanguage]", self.config.target_language)

        return [
            {"role": "system", "content": prompt},
            {"role": "user", "content": input_content}
        ]

    def _print_all_batch_logs(self):
        """统一打印所有批次的日志"""
        if not self.batch_logs:
            return
            
        logger.info("================ 字幕优化结果汇总 ================")

        def is_format_change_only(original, optimized):
            """判断是否只有格式变化（大小写和标点符号）"""
            import string
            # 忽略大小写和标点符号后比较
            original_normalized = original.lower().translate(str.maketrans('', '', string.punctuation))
            optimized_normalized = optimized.lower().translate(str.maketrans('', '', string.punctuation))
            return original_normalized == optimized_normalized

        def is_wrong_replacement(original, optimized):
            """检测是否存在错误的替换（替换了不相关的词）"""
            import re
            # 提取所有单词
            original_words = set(re.findall(r'\b\w+\b', original.lower()))
            optimized_words = set(re.findall(r'\b\w+\b', optimized.lower()))
            # 找出被替换的词
            removed_words = original_words - optimized_words
            added_words = optimized_words - original_words
            # 如果替换前后的词没有相似性，可能是错误替换
            if removed_words and added_words:
                for removed in removed_words:
                    for added in added_words:
                        # 如果原词和新词完全不同（编辑距离过大），判定为错误替换
                        if len(removed) > 3 and len(added) > 3 and not any(c in removed for c in added):
                            return True
            return False
            
        # 统计计数
        format_changes = 0
        content_changes = 0
        wrong_changes = 0
            
        # 按ID排序输出
        sorted_ids = sorted(self.batch_logs.keys())
        for i, id_num in enumerate(sorted_ids):
            log = self.batch_logs[id_num]
            original = log['original']
            optimized = log['optimized']
            
            # 判断改动类型并使用不同级别输出日志
            if is_format_change_only(original, optimized):
                format_changes += 1
                logger.debug(f"字幕ID {id_num} - 格式优化:")
                logger.debug(f"原始: {original}")
                logger.debug(f"优化: {optimized}")
                # 格式优化使用debug级别分隔线
                if i < len(sorted_ids) - 1:
                    logger.debug("-" * 50)
            else:
                if is_wrong_replacement(original, optimized):
                    wrong_changes += 1
                    logger.error(f"字幕ID {id_num} - 可能存在错误替换:")
                    logger.error(f"原始: {original}")
                    logger.error(f"优化: {optimized}")
                    # 错误替换使用error级别分隔线
                    if i < len(sorted_ids) - 1:
                        logger.error("-" * 50)
                else:
                    content_changes += 1
                    logger.info(f"字幕ID {id_num} - 内容优化:")
                    logger.info(f"原始: {original}")
                    logger.info(f"优化: {optimized}")
                    # 内容优化使用info级别分隔线
                    if i < len(sorted_ids) - 1:
                        logger.info("-" * 50)

            if 'translation' in log:
                # logger.debug(f"翻译: {log['translation']}")
                pass
            if 'revised_translation' in log:
                # 反思相关信息使用info级别
                logger.info(f"反思建议: {log['revise_suggestions']}")
                logger.info(f"反思后翻译: {log['revised_translation']}")
                if i < len(sorted_ids) - 1:
                    logger.info("-" * 50)
        
        # 输出统计信息
        logger.info("统计信息:")
        logger.info(f"格式优化数量: {format_changes}")
        logger.info(f"内容修改数量: {content_changes}")
        if wrong_changes > 0:
            logger.error(f"疑似错误替换数量: {wrong_changes}")
        logger.info(f"总修改数量: {format_changes + content_changes + wrong_changes}")
        logger.info("================ 字幕优化结果结束 ================")
        # 清空日志字典
        self.batch_logs.clear()

    @retry.retry(tries=2)
    def _reflect_translate(self, original_subtitle: Dict[str, str], 
                          summary_content: Dict) -> List[Dict]:
        """反思翻译字幕"""
        subtitle_keys = sorted(map(int, original_subtitle.keys()))
        logger.info(f"[+]正在反思翻译字幕：{subtitle_keys[0]} - {subtitle_keys[-1]}")
        message = self._create_translate_message(original_subtitle, summary_content, reflect=True)
        response = self.client.chat.completions.create(
            model=self.config.llm_model,
            stream=False,
            messages=message,
            temperature=0.7
        )
        response_content = parse_llm_response(response.choices[0].message.content)

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

            # 收集日志而不是直接输出
            if (translated_text["original"] != translated_text["optimized"] or 
                translated_text["translation"] != translated_text["revised_translation"]):
                # 使用字典存储，ID作为键
                self.batch_logs[k] = {
                    'original': translated_text['original'],
                    'optimized': translated_text['optimized'],
                    'translation': translated_text['translation'],
                    'revised_translation': translated_text['revised_translation'],
                    'revise_suggestions': translated_text['revise_suggestions']
                }

        return translated_subtitle

    @retry.retry(tries=2)
    def _translate(self, original_subtitle: Dict[str, str], 
                  summary_content: Dict) -> List[Dict]:
        """翻译字幕"""
        subtitle_keys = sorted(map(int, original_subtitle.keys()))
        logger.info(f"[+]正在翻译字幕：{subtitle_keys[0]} - {subtitle_keys[-1]}")
        message = self._create_translate_message(original_subtitle, summary_content, reflect=False)
        response = self.client.chat.completions.create(
            model=self.config.llm_model,
            stream=False,
            messages=message,
            temperature=0.7
        )
        response_content = parse_llm_response(response.choices[0].message.content)

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

            # 收集日志而不是直接输出
            if translated_text["original"] != translated_text["optimized"]:
                # 使用字典存储，ID作为键
                self.batch_logs[k] = {
                    'original': translated_text['original'],
                    'optimized': translated_text['optimized'],
                    'translation': translated_text['translation']
                }

        return translated_subtitle