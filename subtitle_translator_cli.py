import dotenv
dotenv.load_dotenv()

import argparse
import os
from pathlib import Path
from typing import Dict, List, Optional

from subtitle_processor.optimizer import SubtitleOptimizer
from subtitle_processor.summarizer import SubtitleSummarizer
from subtitle_processor.spliter import merge_segments
from subtitle_processor.config import SubtitleConfig, SRT_SUFFIX, OUTPUT_SUFFIX, EN_OUTPUT_SUFFIX, get_default_config
from subtitle_processor.data import load_subtitle, SubtitleData
from utils.test_opanai import test_openai
from utils.logger import setup_logger

# 配置日志
logger = setup_logger("subtitle_translator_cli")

class SubtitleTranslator:
    def __init__(self):
        self.config = get_default_config()
        self.summarizer = SubtitleSummarizer(config=self.config)

    def translate(self, input_file: str, en_output: str, zh_output: str, llm_model: str = None, reflect: bool = False) -> None:
        """翻译字幕文件
        
        Args:
            input_file: 输入字幕文件路径
            en_output: 英文字幕输出路径
            zh_output: 中文字幕输出路径
            llm_model: 使用的语言模型
            reflect: 是否启用反思翻译
        """
        try:
            logger.info("字幕处理任务开始...")     
            # 初始化翻译环境
            self._init_translation_env(llm_model)
            
            # 加载字幕文件
            asr_data = load_subtitle(input_file)
            
            # 检查是否需要重新断句
            if asr_data.is_word_timestamp():
                model = "gpt-4o-mini"
                logger.info(f"正在使用{model}断句...")
                asr_data = merge_segments(asr_data, model=model, 
                                       num_threads=self.config.thread_num, 
                                       max_word_count_cjk=self.config.max_word_count_cjk, 
                                       max_word_count_english=self.config.max_word_count_english)
            
            # 获取字幕摘要
            summarize_result = self._get_subtitle_summary(asr_data, input_file)
            
            # 翻译字幕
            translate_result = self._translate_subtitles(asr_data, summarize_result, reflect)
            
            # 保存字幕
            asr_data.save_translations_to_files(
                translate_result,
                en_output,
                zh_output
            )
                
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

    def _get_subtitle_summary(self, asr_data: SubtitleData, input_file: str) -> Dict:
        """获取字幕内容摘要"""
        logger.info(f"正在使用 {self.config.llm_model} 总结字幕...")
        summarize_result = self.summarizer.summarize(asr_data.to_txt(), input_file)
        logger.info(f"总结字幕内容:{summarize_result.get('summary')}")
        return summarize_result

    def _translate_subtitles(self, asr_data: SubtitleData, summarize_result: str, reflect: bool = False) -> List[Dict]:
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

def main():
    parser = argparse.ArgumentParser(description="翻译字幕文件")
    parser.add_argument("input_file", help="输入的字幕文件路径")
    parser.add_argument("-r", "--reflect", action="store_true", help="是否启用反思翻译")
    parser.add_argument("-m", "--llm_model", help="LLM模型", default=None)
    args = parser.parse_args()

    try:
        # 处理文件名
        base_path = Path(args.input_file)
        base_name = base_path.stem
        # 只移除末尾的 _en 或 _zh 后缀
        if base_name.endswith('_en'):
            base_name = base_name[:-3]
        elif base_name.endswith('_zh'):
            base_name = base_name[:-3]
        output_dir = base_path.parent
        en_output = str(output_dir / f"{base_name}_en.srt")
        zh_output = str(output_dir / f"{base_name}_zh.srt")

        # 初始化翻译器并开始翻译
        translator = SubtitleTranslator()
        print(f"\n=================== 正在翻译 {base_name} ===================\n")
        translator.translate(
            input_file=args.input_file,
            en_output=en_output,
            zh_output=zh_output,
            llm_model=args.llm_model,
            reflect=args.reflect
        )
    except Exception as e:
        logger.error(f"发生错误: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
