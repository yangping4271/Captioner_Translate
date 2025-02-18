import argparse
import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

from subtitle_processor.optimizer import SubtitleOptimizer
from subtitle_processor.summarizer import SubtitleSummarizer
from subtitle_processor.spliter import merge_segments
from subtitle_processor.config import SubtitleConfig, SRT_SUFFIX, OUTPUT_SUFFIX, EN_OUTPUT_SUFFIX
from bk_asr.ASRData import from_subtitle_file, ASRData, ASRDataSeg
from utils.test_opanai import test_openai
from utils.logger import setup_logger

import dotenv
dotenv.load_dotenv()

# 配置日志
logger = setup_logger("subtitle_translator_cli")

class SubtitleTranslator:
    def __init__(self):
        self.config = SubtitleConfig()
        self.summarizer = SubtitleSummarizer(config=self.config)

    def translate(self, input_file: str, output_file: str, llm_model: str, reflect: bool) -> None:
        """翻译字幕文件"""
        try:
            logger.info("字幕处理任务开始...")     
            # 初始化翻译环境
            self._init_translation_env(llm_model)
            
            # 加载字幕文件
            asr_data = self._load_subtitle_file(input_file)
            
            # 检查是否需要重新断句
            if asr_data.is_word_timestamp():
                logger.info(f"正在使用{self.config.llm_model}断句...")
                asr_data = merge_segments(asr_data, model=self.config.llm_model, 
                                       num_threads=self.config.thread_num, 
                                       max_word_count_cjk=self.config.max_word_count_cjk, 
                                       max_word_count_english=self.config.max_word_count_english)
            
            # 获取字幕摘要
            summarize_result = self._get_subtitle_summary(asr_data)
            
            # 翻译字幕
            translate_result = self._translate_subtitles(asr_data, summarize_result, reflect)
            
            # 保存字幕
            self._save_subtitles(asr_data, translate_result, input_file, output_file)
                
        except Exception as e:
            logger.exception(f"翻译失败: {str(e)}")
            raise

    def _init_translation_env(self, llm_model: str) -> None:
        """初始化翻译环境"""
        if llm_model:
            self.config.llm_model = llm_model
        
        # 测试 OpenAI API
        if not test_openai(self.config.openai_base_url, self.config.openai_api_key, self.config.llm_model):
            raise Exception("OpenAI API 测试失败, 请检查设置")

        logger.info(f"使用 {self.config.openai_base_url} 作为API端点")
        logger.info(f"使用 {self.config.llm_model} 作为LLM模型")

    def _load_subtitle_file(self, input_file: str) -> ASRData:
        """加载字幕文件"""
        if not os.path.exists(input_file):
            raise Exception(f"输入文件 {input_file} 不存在")
        if not input_file.endswith(SRT_SUFFIX):
            raise Exception("仅支持srt格式字幕文件")
            
        return from_subtitle_file(input_file)

    def _get_subtitle_summary(self, asr_data: ASRData) -> str:
        """获取字幕内容摘要"""
        logger.info(f"正在使用 {self.config.llm_model} 总结字幕...")
        summarize_result = self.summarizer.summarize(asr_data.to_txt())
        logger.info(f"总结字幕内容:{summarize_result}")
        return summarize_result

    def _translate_subtitles(self, asr_data: ASRData, summarize_result: str, reflect: bool = False) -> List[Dict]:
        """翻译字幕内容"""
        logger.info(f"正在使用 {self.config.llm_model} 翻译字幕...")
        try:
            translator = SubtitleOptimizer(
                config=self.config,
                need_reflect=reflect
            )
            translate_result = translator.translate(asr_data, summarize_result)
            return translate_result
        except Exception as e:
            logger.error(f"翻译失败: {str(e)}")
            raise

    def _save_subtitles(self, asr_data, translate_result: List[Dict], input_file: str, output_file: str) -> None:
        """
        保存翻译结果
        """
        # 创建输出目录
        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        # 构建文件路径
        base_name = os.path.splitext(os.path.basename(input_file))[0]
        en_path = os.path.join(os.path.dirname(output_file), f"{base_name}_optimized.srt")
        zh_path = os.path.join(os.path.dirname(output_file), f"{base_name}_translated.srt")

        # 保存优化后的英文字幕
        optimized_subtitles = {item["id"]: item["optimized"] for item in translate_result}
        self._save_srt_file(asr_data, optimized_subtitles, en_path, "优化")

        # 保存翻译后的中文字幕
        if any("revised_translation" in item for item in translate_result):
            # 如果有反思翻译结果，使用反思后的翻译
            translated_subtitles = {item["id"]: item["revised_translation"] for item in translate_result}
        else:
            # 否则使用普通翻译结果
            translated_subtitles = {item["id"]: item["translation"] for item in translate_result}
        self._save_srt_file(asr_data, translated_subtitles, zh_path, "翻译")

    def _save_srt_file(self, asr_data: ASRData, subtitle_dict: Dict, 
                       output_path: str, operation: str = "处理") -> None:
        """通用的字幕保存方法"""
        # 创建输出目录
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # 生成SRT格式的字幕内容
        srt_lines = []
        logger.info(f"ASR数据段数: {len(asr_data.segments)}")
        logger.info(f"字幕字典内容: {subtitle_dict}")
        for i, subtitle_text in enumerate(asr_data.segments, 1):
            if i not in subtitle_dict:
                logger.warning(f"字幕 {i} 不在字典中")
                continue
            srt_lines.extend([
                str(i),
                subtitle_text.to_srt_ts(),
                subtitle_dict[i],
                ""  # 空行分隔
            ])

        # 写入文件
        srt_content = "\n".join(srt_lines)
        logger.info(f"生成的SRT内容:\n{srt_content}")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(srt_content)

        if not os.path.exists(output_path):
            raise Exception(f"字幕{operation}失败...")
        logger.info(f"{operation}后的字幕已保存至: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="翻译字幕文件")
    parser.add_argument("input_file", help="输入的字幕文件路径")
    parser.add_argument("-r", "--reflect", action="store_true", help="是否启用反思翻译")
    parser.add_argument("-o", "--output_dir", default="output", help="输出目录路径")
    parser.add_argument("-m", "--llm_model", help="LLM模型", default=None)
    args = parser.parse_args()

    try:
        # 创建输出目录
        os.makedirs(args.output_dir, exist_ok=True)

        # 构建输出文件路径
        base_name = os.path.splitext(os.path.basename(args.input_file))[0]
        output_file = os.path.join(args.output_dir, f"{base_name}.srt")

        # 初始化翻译器并开始翻译
        translator = SubtitleTranslator()
        print(f"\n=================== 正在翻译 {base_name} ===================\n")
        translator.translate(
            input_file=args.input_file,
            output_file=output_file,
            llm_model=args.llm_model,
            reflect=args.reflect
        )
    except Exception as e:
        logger.error(f"发生错误: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
