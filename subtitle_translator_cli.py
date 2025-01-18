#!/usr/bin/env python3
# subtitle_translator.py

import argparse
import json
import os
import sys
import datetime
from pathlib import Path
from typing import Optional, Dict, Any
import dotenv

dotenv.load_dotenv()

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from app.core.entities import Task
from app.core.thread.subtitle_optimization_thread import SubtitleOptimizationThread

class SubtitleTranslator:
    def __init__(self, config_path: Optional[str] = None):
        self.config = self._load_config(config_path)

    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        default_config = {
            "llm_model": os.getenv('LLM_MODEL'),
            "api_key": os.getenv('OPENAI_API_KEY'),
            "api_base": os.getenv('OPENAI_BASE_URL'),

            "target_language": "中文",
            "temperature": 0.7,
            "subtitle_layout": "仅译文",
            "thread_num": 10,
            "batch_size": 20
        }

        if config_path and os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
                default_config.update(user_config)

        return default_config

    def translate(self, input_file: str, output_file: str,
                 optimize: bool = True, translate: bool = True,
                 layout: Optional[str] = None) -> None:
        try:
            # 创建任务配置
            task = Task(
                id=0,
                queued_at=datetime.datetime.now(),
                started_at=datetime.datetime.now(),
                completed_at=None,
                status=Task.Status.PENDING,
                fraction_downloaded=0,
                work_dir=str(Path(input_file).parent),
                file_path=str(input_file),
                url="",
                source=Task.Source.FILE_IMPORT,
                original_language=None,
                target_language=self.config["target_language"],
                transcribe_language=None,
                whisper_model=None,
                video_info=None,
                audio_format=None,
                audio_save_path=None,
                transcribe_model=None,
                use_asr_cache=True,
                need_word_time_stamp=False,
                original_subtitle_save_path=str(input_file),
                base_url=self.config["api_base"],
                api_key=self.config["api_key"],
                llm_model=self.config["llm_model"],
                need_translate=translate,
                need_optimize=optimize,
                result_subtitle_save_path=str(output_file),
                subtitle_layout=layout or self.config["subtitle_layout"],
                video_save_path=None,
                soft_subtitle=False,
                subtitle_style_srt=None,
                thread_num=self.config["thread_num"],
                batch_size=self.config["batch_size"]
            )
            
            # 创建并运行优化线程
            optimization_thread = SubtitleOptimizationThread(task)
            optimization_thread.run()
            
            # 判断输出文件是否存在
            if os.path.exists(output_file):
                print(f"处理完成! 文件已保存至: {output_file}")
        except Exception as e:
            print(f"处理失败: {str(e)}")
            raise

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
