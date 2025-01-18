#!/usr/bin/env python3
# subtitle_translator.py

import argparse
import json
import os
import sys
import datetime
import threading
from pathlib import Path
from typing import Optional, Dict, Any
import dotenv

dotenv.load_dotenv()

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from app.core.subtitle_processor.optimizer import SubtitleOptimizer
from app.core.subtitle_processor.summarizer import SubtitleSummarizer
from app.core.bk_asr.ASRData import from_subtitle_file
from app.core.subtitle_processor.spliter import merge_segments
from app.core.utils.test_opanai import test_openai
from app.core.utils.logger import setup_logger

# 配置日志
logger = setup_logger("subtitle_translator_cli")

FREE_API_CONFIGS = {
    "ddg": {
        "base_url": "http://ddg.bkfeng.top/v1",
        "api_key": "Hey-man-This-free-server-is-convenient-for-beginners-Please-do-not-use-for-personal-use-Server-just-has-limited-concurrency",
        "llm_model": "gpt-4o-mini",
        "thread_num": 5,
        "batch_size": 10
    },
    "zhipu": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "api_key": "c96c2f6ce767136cdddc3fef1692c1de.H27sLU4GwuUVqPn5",
        "llm_model": "glm-4-flash",
        "thread_num": 10,
        "batch_size": 10
    }
}

class SubtitleTranslator:
    def __init__(self, config_path: Optional[str] = None):
        self.config = self._load_config(config_path)
        self.subtitle_length = 0
        self.finished_subtitle_length = 0
        self.custom_prompt_text = ""
        self.llm_result_logger = None

    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        default_config = {
            "llm_model": os.getenv('LLM_MODEL'),
            "api_key": os.getenv('OPENAI_API_KEY'),
            "api_base": os.getenv('OPENAI_BASE_URL'),

            "target_language": "简体中文",
            "temperature": 0.7,
            "subtitle_layout": "译文在上",
            "thread_num": 10,
            "batch_size": 20,
            "max_word_count_cjk": 18,
            "max_word_count_english": 12,
            "need_split": True,
            "faster_whisper_one_word": True
        }

        if config_path and os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
                default_config.update(user_config)

        return default_config

    def _setup_api_config(self):
        """设置API配置，返回base_url, api_key, llm_model, thread_num, batch_size"""
        if self.config["api_base"] and self.config["api_key"]:
            if not test_openai(self.config["api_base"], self.config["api_key"], self.config["llm_model"])[0]:
                raise Exception("OpenAI API 测试失败, 请检查设置")
            return (self.config["api_base"], self.config["api_key"], self.config["llm_model"],
                   self.config["thread_num"], self.config["batch_size"])
        
        logger.info("尝试使用自带的API配置")
        # 遍历配置字典找到第一个可用的API
        for config in FREE_API_CONFIGS.values():
            if test_openai(config["base_url"], config["api_key"], config["llm_model"])[0]:
                return (config["base_url"], config["api_key"], config["llm_model"],
                       config["thread_num"], config["batch_size"])
        
        logger.error("自带的API配置暂时不可用，请配置自己的API")
        raise Exception("自带的API配置暂时不可用，请配置自己的大模型API")

    def translate(self, input_file: str, output_file: str,
                 optimize: bool = True, translate: bool = True,
                 layout: Optional[str] = None) -> None:
        try:
            logger.info(f"\n===========字幕优化任务开始===========")
            logger.info(f"时间：{datetime.datetime.now()}")
            
            # 获取API配置
            logger.info("开始验证API配置...")
            base_url, api_key, llm_model, thread_num, batch_size = self._setup_api_config()
            logger.info(f"使用 {llm_model} 作为LLM模型")
            os.environ['OPENAI_BASE_URL'] = base_url
            os.environ['OPENAI_API_KEY'] = api_key

            # 检查文件
            if not os.path.exists(input_file):
                raise Exception(f"输入文件 {input_file} 不存在")
            if not Path(input_file).suffix in ['.srt', '.vtt', '.ass']:
                raise Exception("字幕文件格式不支持")

            logger.info("开始优化字幕...")
            asr_data = from_subtitle_file(input_file)

            # 检查是否需要合并重新断句
            split_path = input_file.replace('.srt', '_en.srt')
            if not asr_data.is_word_timestamp() and self.config["need_split"] and self.config["faster_whisper_one_word"]:
                asr_data.split_to_word_segments()
            if asr_data.is_word_timestamp():
                logger.info("正在字幕断句...")
                asr_data = merge_segments(asr_data, model=llm_model, 
                                       num_threads=thread_num, 
                                       max_word_count_cjk=self.config["max_word_count_cjk"], 
                                       max_word_count_english=self.config["max_word_count_english"])
                asr_data.save(save_path=split_path)

            # 制作成请求llm接口的格式 {{"1": "original_subtitle"},...}
            subtitle_json = {str(k): v["original_subtitle"] for k, v in asr_data.to_json().items()}
            self.subtitle_length = len(subtitle_json)

            if translate or optimize:
                summarize_result = self.custom_prompt_text.strip()
                logger.info("总结字幕...")
                if not summarize_result:
                    summarizer = SubtitleSummarizer(model=llm_model)
                    summarize_result = summarizer.summarize(asr_data.to_txt())
                logger.info(f"总结字幕内容:{summarize_result}")
                
                if translate:
                    logger.info("正在优化+翻译...")
                    need_reflect = False
                    optimizer = SubtitleOptimizer(
                        summary_content=summarize_result,
                        model=llm_model,
                        target_language=self.config["target_language"],
                        batch_num=batch_size,
                        thread_num=thread_num,
                        llm_result_logger=self.llm_result_logger,
                        need_remove_punctuation=False,
                        cjk_only=True
                    )
                    optimizer_result = optimizer.optimizer_multi_thread(subtitle_json, translate=True,
                                                                     reflect=need_reflect,
                                                                     callback=self.callback)
                elif optimize:
                    logger.info("正在优化字幕...")
                    optimizer = SubtitleOptimizer(summary_content=summarize_result, model=llm_model,
                                               batch_num=batch_size, thread_num=thread_num,
                                               llm_result_logger=self.llm_result_logger)
                    optimizer_result = optimizer.optimizer_multi_thread(subtitle_json, callback=self.callback)

                # 替换优化或者翻译后的字幕
                for i, subtitle_text in optimizer_result.items():
                    seg = asr_data.segments[int(i) - 1]
                    seg.text = subtitle_text

            # 保存字幕
            subtitle_layout = layout or self.config["subtitle_layout"]
            if output_file.endswith(".ass"):
                asr_data.to_ass(style_str=None, layout=subtitle_layout, save_path=output_file)
            else:
                asr_data.save(save_path=output_file, ass_style=None, layout=subtitle_layout)

            if not os.path.exists(output_file):
                raise Exception("字幕优化失败...")

            logger.info("优化完成")
            print(f"处理完成! 文件已保存至: {output_file}")
        except Exception as e:
            logger.exception(f"优化失败: {str(e)}")
            raise

    def callback(self, result: Dict):
        self.finished_subtitle_length += len(result)
        progress = int((self.finished_subtitle_length / self.subtitle_length) * 100)
        logger.info(f"{progress}% 处理字幕")

def main():
    parser = argparse.ArgumentParser(description='字幕翻译工具')
    parser.add_argument('input', help='输入字幕文件路径')
    parser.add_argument('output', nargs='?', help='输出字幕文件路径')
    parser.add_argument('--config', help='配置文件路径')
    parser.add_argument('--no-optimize', action='store_true', help='禁用字幕优化')
    parser.add_argument('--no-translate', action='store_true', help='禁用字幕翻译')
    parser.add_argument('--layout', choices=['原文在上', '译文在上', '仅原文', '仅译文'],
                      help='字幕布局方式')
    parser.add_argument('-m', '--model', type=str, help="指定使用的语言模型")
    args = parser.parse_args()
    
    if not args.output:
        args.output = args.input.replace('.srt', '_zh.srt')
    
    if not os.path.exists(args.input):
        print(f"错误: 输入文件 {args.input} 不存在")
        return

    output_dir = os.path.dirname(args.output)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    try:
        translator = SubtitleTranslator(args.config)
        translator.config['llm_model'] = args.model if args.model else translator.config['llm_model']
        print(f"\n-----------------正在翻译 {args.input} 到 {args.output}-----------------")
        translator.translate(
            input_file=args.input,
            output_file=args.output,
            optimize=not args.no_optimize,
            translate=not args.no_translate,
            layout=args.layout
        )
    except Exception as e:
        print(f"发生错误: {str(e)}")

if __name__ == "__main__":
    main()
