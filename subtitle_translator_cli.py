import argparse
import os
from pathlib import Path
from typing import Dict, Any

from subtitle_processor.optimizer import SubtitleOptimizer
from subtitle_processor.summarizer import SubtitleSummarizer
from subtitle_processor.spliter import merge_segments
from bk_asr.ASRData import from_subtitle_file, ASRData, ASRDataSeg
from utils.test_opanai import test_openai
from utils.logger import setup_logger

import dotenv
dotenv.load_dotenv()

# 配置日志
logger = setup_logger("subtitle_translator_cli")

class SubtitleTranslator:
    def __init__(self):
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        return {
            "llm_model": os.getenv('LLM_MODEL'),
            "api_key": os.getenv('OPENAI_API_KEY'),
            "api_base": os.getenv('OPENAI_BASE_URL'),
            "target_language": "简体中文",
            "thread_num": 18,
            "batch_size": 20,
            "max_word_count_cjk": 18,
            "max_word_count_english": 14,
            "need_reflect": False
        }

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
                logger.info(f"正在使用{llm_model}断句...")
                asr_data = merge_segments(asr_data, model=llm_model, 
                                       num_threads=self.config["thread_num"], 
                                       max_word_count_cjk=self.config["max_word_count_cjk"], 
                                       max_word_count_english=self.config["max_word_count_english"])
            
            # 获取字幕摘要
            summarize_result = self._get_subtitle_summary(asr_data, llm_model)
            
            # 翻译字幕
            translate_result = self._translate_subtitles(asr_data, summarize_result, llm_model, reflect)
            
            # 保存字幕
            self._save_subtitles(asr_data, translate_result, input_file, output_file)
                
        except Exception as e:
            logger.exception(f"翻译失败: {str(e)}")
            raise

    def _init_translation_env(self, llm_model: str) -> None:
        """初始化翻译环境"""
        llm_model = llm_model or self.config["llm_model"]
        api_base = self.config["api_base"]
        api_key = self.config["api_key"]
        
        # 先设置环境变量
        os.environ['OPENAI_BASE_URL'] = api_base
        os.environ['OPENAI_API_KEY'] = api_key
        
        # 然后测试 OpenAI API
        if not test_openai(api_base, api_key, llm_model):
            raise Exception("OpenAI API 测试失败, 请检查设置")

        logger.info(f"使用 {api_base} 作为API端点")
        logger.info(f"使用 {llm_model} 作为LLM模型")

    def _load_subtitle_file(self, input_file: str) -> ASRData:
        """加载字幕文件"""
        if not os.path.exists(input_file):
            raise Exception(f"输入文件 {input_file} 不存在")
        if not input_file.endswith('.srt'):
            raise Exception("仅支持srt格式字幕文件")
            
        return from_subtitle_file(input_file)

    def _get_subtitle_summary(self, asr_data: ASRData, llm_model: str) -> str:
        """获取字幕内容摘要"""
        model = llm_model or self.config["llm_model"]
        logger.info(f"正在使用 {model} 总结字幕...")
        summarizer = SubtitleSummarizer(model=model)
        summarize_result = summarizer.summarize(asr_data.to_txt())
        logger.info(f"总结字幕内容:{summarize_result}")
        return summarize_result

    def _translate_subtitles(self, asr_data: ASRData, summarize_result: str, 
                           llm_model: str, reflect: bool) -> Dict:
        """翻译字幕内容"""
        model = llm_model or self.config["llm_model"]
        logger.info(f"正在使用 {model} 翻译字幕...")
        translator = SubtitleOptimizer(
            summary_content=summarize_result,
            model=model,
            target_language=self.config["target_language"],
            batch_num=self.config["batch_size"],
            thread_num=self.config["thread_num"],
            need_remove_punctuation=False,
            cjk_only=True
        )
        
        subtitle_json = {str(k): v["original_subtitle"] 
                        for k, v in asr_data.to_json().items()}
        return translator.translate_multi_thread(subtitle_json,
                                              reflect=reflect or self.config["need_reflect"])

    def _save_subtitles(self, asr_data: ASRData, translate_result: Dict,
                       input_file: str, output_file: str) -> None:
        """保存翻译结果"""
        # 保存优化后的英文字幕
        en_path = input_file.replace('.srt', '_en.srt')
        self._save_optimized_subtitles(asr_data, translate_result["optimized_subtitles"], en_path)
        
        # 保存中文翻译字幕
        self._save_translated_subtitles(asr_data, translate_result["translated_subtitles"]["translated_subtitles"], 
                                      output_file)

    def _save_optimized_subtitles(self, asr_data: ASRData, optimized_subtitles: Dict, 
                                 output_path: str) -> None:
        """保存优化后的原文字幕"""
        optimized_segments = []
        for i, subtitle_text in enumerate(asr_data.segments, 1):
            if str(i) not in optimized_subtitles:
                continue
            optimized_segments.append(ASRDataSeg(
                text=optimized_subtitles[str(i)],
                start_time=subtitle_text.start_time,
                end_time=subtitle_text.end_time
            ))
        
        optimized_asr_data = ASRData(optimized_segments)
        optimized_asr_data.save(save_path=output_path)
        if not os.path.exists(output_path):
            raise Exception("字幕优化失败...")
        logger.info(f"优化后的字幕已保存至: {output_path}")

    def _save_translated_subtitles(self, asr_data: ASRData, translated_subtitles: Dict,
                                 output_path: str) -> None:
        """保存翻译后的字幕"""
        translated_segments = []
        for i, subtitle_text in enumerate(asr_data.segments, 1):
            if str(i) not in translated_subtitles:
                continue
            texts = translated_subtitles[str(i)].split("\n")
            translated_text = texts[1] if len(texts) > 1 else texts[0]
            translated_segments.append(ASRDataSeg(
                text=translated_text,
                start_time=subtitle_text.start_time,
                end_time=subtitle_text.end_time
            ))
        
        translated_asr_data = ASRData(translated_segments)
        translated_asr_data.save(save_path=output_path)
        if not os.path.exists(output_path):
            raise Exception("字幕翻译失败...")
        logger.info(f"翻译后的字幕已保存至: {output_path}")


def main():
    parser = argparse.ArgumentParser(description='字幕翻译工具')
    parser.add_argument('input', help='输入字幕文件路径')
    parser.add_argument('-m', '--llm_model', help='LLM模型', default=None)
    parser.add_argument('-r', '--reflect', help='是否启用反思翻译', action='store_true')
    args = parser.parse_args()
    input_file = args.input
    output_file = input_file.replace('.srt', '_zh.srt')
    
    if not os.path.exists(input_file):
        logger.error(f"错误: 输入文件 {input_file} 不存在")
        return

    try:
        translator = SubtitleTranslator()
        print(f"\n=================== 正在翻译 {input_file.replace('.srt', '')} ===================\n")
        translator.translate(
            input_file=input_file,
            output_file=output_file,
            llm_model=args.llm_model,
            reflect=args.reflect
        )
    except Exception as e:
        logger.exception(f"发生错误: {str(e)}")

if __name__ == "__main__":
    main()
