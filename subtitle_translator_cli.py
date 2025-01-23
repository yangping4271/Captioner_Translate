import argparse
import os
from pathlib import Path
from typing import Dict, Any

from subtitle_processor.optimizer import SubtitleOptimizer
from subtitle_processor.summarizer import SubtitleSummarizer
from subtitle_processor.spliter import merge_segments
from bk_asr.ASRData import from_subtitle_file
from utils.test_opanai import test_openai
from utils.logger import setup_logger

import dotenv
dotenv.load_dotenv()

# 配置日志
logger = setup_logger("subtitle_translator_cli")

class SubtitleTranslator:
    def __init__(self):
        self.config = self._load_config()
        self.subtitle_length = 0
        self.finished_subtitle_length = 0
        self.custom_prompt_text = ""
        self.llm_result_logger = None

    def _load_config(self) -> Dict[str, Any]:
        return {
            "llm_model": os.getenv('LLM_MODEL'),
            "api_key": os.getenv('OPENAI_API_KEY'),
            "api_base": os.getenv('OPENAI_BASE_URL'),
            "target_language": "简体中文",
            "subtitle_layout": "仅译文",
            "thread_num": 15,
            "batch_size": 10,
            "max_word_count_cjk": 18,
            "max_word_count_english": 14,
            "need_optimize": False,
            "need_reflect": False
        }

    def translate(self, input_file: str, output_file: str, llm_model: str) -> None:
        try:
            logger.info("字幕处理任务开始...")     
            # 获取API配置
            llm_model = llm_model or self.config["llm_model"]
            api_base = self.config["api_base"]
            api_key = self.config["api_key"]
            
            if not test_openai(api_base, api_key, llm_model):
                raise Exception("OpenAI API 测试失败, 请检查设置")

            logger.info(f"使用 {api_base} 作为API端点")
            logger.info(f"使用 {llm_model} 作为LLM模型")
            os.environ['OPENAI_BASE_URL'] = api_base
            os.environ['OPENAI_API_KEY'] = api_key

            # 检查文件
            if not os.path.exists(input_file):
                raise Exception(f"输入文件 {input_file} 不存在")
            if not Path(input_file).suffix in ['.srt', '.vtt', '.ass']:
                raise Exception("字幕文件格式不支持")

            asr_data = from_subtitle_file(input_file)

            # 检查是否需要重新断句
            split_path = input_file.replace('.srt', '_en.srt')
            if self.config["need_optimize"] and not asr_data.is_word_timestamp():
                logger.info("开始优化字幕...")
                asr_data.split_to_word_segments()
            if asr_data.is_word_timestamp():
                logger.info("正在字幕断句...")
                asr_data = merge_segments(asr_data, model=llm_model, 
                                       num_threads=self.config["thread_num"], 
                                       max_word_count_cjk=self.config["max_word_count_cjk"], 
                                       max_word_count_english=self.config["max_word_count_english"])
                asr_data.save(save_path=split_path)
                if os.path.exists(split_path):
                    logger.info(f"字幕断句完成，已保存至: {split_path}")
                else:
                    raise Exception("字幕断句失败...")

            summarize_result = self.custom_prompt_text.strip()
            logger.info("总结字幕...")
            if not summarize_result:
                summarizer = SubtitleSummarizer(model=llm_model)
                summarize_result = summarizer.summarize(asr_data.to_txt())
                logger.info(f"总结字幕内容:{summarize_result}")
                
            logger.info("正在翻译...")
            optimizer = SubtitleOptimizer(
                summary_content=summarize_result,
                model=llm_model,
                target_language=self.config["target_language"],
                batch_num=self.config["batch_size"],
                thread_num=self.config["thread_num"],
                need_remove_punctuation=False,
                cjk_only=True
            )

            if self.config["need_optimize"]:
                # 制作成请求llm接口的格式 {{"1": "original_subtitle"},...}
                subtitle_json = {str(k): v["original_subtitle"] for k, v in asr_data.to_json().items()}
                self.subtitle_length = len(subtitle_json)
                optimizer_result = optimizer.optimizer_multi_thread(subtitle_json,
                                                               translate=False)

                # 替换优化后的字幕  
                for i, subtitle_text in optimizer_result.items():
                    seg = asr_data.segments[int(i) - 1]
                    seg.text = subtitle_text
            else:
                subtitle_json = {str(k): v["original_subtitle"] for k, v in asr_data.to_json().items()}
                self.subtitle_length = len(subtitle_json)
                translate_result = optimizer.optimizer_multi_thread(subtitle_json,
                                                            translate=True,
                                                            reflect=self.config["need_reflect"])

                # 替换优化或者翻译后的字幕
                for i, subtitle_text in translate_result.items():
                    seg = asr_data.segments[int(i) - 1]
                    seg.text = subtitle_text

            # 保存字幕
            subtitle_layout = self.config["subtitle_layout"]
            if output_file.endswith(".ass"):
                asr_data.to_ass(style_str=None, layout=subtitle_layout, save_path=output_file)
            else:
                asr_data.save(save_path=output_file, ass_style=None, layout=subtitle_layout)

            if not os.path.exists(output_file):
                raise Exception("字幕优化失败...")

            logger.info("优化完成")
            if os.path.exists(output_file):
                logger.info(f"处理完成! 文件已保存至: {output_file}")
                
        except Exception as e:
            logger.exception(f"优化失败: {str(e)}")
            raise


def main():
    parser = argparse.ArgumentParser(description='字幕翻译工具')
    parser.add_argument('input', help='输入字幕文件路径')
    parser.add_argument('-m', '--llm_model', help='LLM模型', default=None)
    args = parser.parse_args()
    input_file = args.input
    output_file = input_file.replace('.srt', '_zh.srt')
    
    if not os.path.exists(input_file):
        logger.error(f"错误: 输入文件 {input_file} 不存在")
        return

    try:
        translator = SubtitleTranslator()
        print(f"\n=================== 正在翻译 {input_file} ===================\n")
        translator.translate(
            input_file=input_file,
            output_file=output_file,
            llm_model=args.llm_model
        )
    except Exception as e:
        logger.exception(f"发生错误: {str(e)}")

if __name__ == "__main__":
    main()
