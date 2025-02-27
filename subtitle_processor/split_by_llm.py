import re
from typing import List

from openai import OpenAI

from .prompts import SPLIT_SYSTEM_PROMPT
from .config import SubtitleConfig
from utils.logger import setup_logger

logger = setup_logger("subtitle_spliter")

def count_words(text: str) -> int:
    """
    统计文本中英文单词数
    Args:
        text: 输入文本，英文
    Returns:
        int: 英文单词数
    """
    english_text = re.sub(r'[\u4e00-\u9fff]', ' ', text)
    english_words = english_text.strip().split()
    return len(english_words)

def split_by_llm(text: str,
                model: str = "gpt-4o-mini",
                max_word_count_english: int = 14,
                max_retries: int = 3) -> List[str]:
    """
    使用LLM拆分句子
    
    Args:
        text: 要拆分的文本
        model: 使用的语言模型
        max_word_count_english: 英文最大单词数
        max_retries: 最大重试次数
        
    Returns:
        List[str]: 拆分后的句子列表
    """
    logger.debug(f"text: \n{text}")
    
    # 初始化客户端
    config = SubtitleConfig()
    client = OpenAI(
        base_url=config.openai_base_url,
        api_key=config.openai_api_key
    )
    
    # 使用系统提示词
    system_prompt = SPLIT_SYSTEM_PROMPT.replace("[max_word_count_english]", str(max_word_count_english))
    
    # 在用户提示中添加对空格的强调
    user_prompt = f"Please use multiple <br> tags to separate the following sentence. Make sure to preserve all spaces and punctuation exactly as they appear in the original text:\n{text}"

    try:
        # 调用API
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2,
            timeout=80
        )
        
        # 处理响应
        result = response.choices[0].message.content
        if not result:
            raise Exception("API返回为空")
        logger.debug(f"API: \n{result}")

        # 清理和分割文本 - 简化处理，保留原始格式
        result = re.sub(r'\n+', '', result)
        
        # 直接按<br>分割，保留原始格式和空格
        segments = result.split("<br>")
        
        # 清理空白行，但保留内部空格
        segments = [seg.strip() for seg in segments if seg.strip()]
        
        # 验证结果
        word_count = count_words(text)
        expected_segments = word_count / max_word_count_english
        actual_segments = len(segments)
        
        if actual_segments < expected_segments * 0.9:
            logger.warning(f"断句数量不足：预期 {expected_segments:.1f}，实际 {actual_segments}")
            
        return segments
        
    except Exception as e:
        if max_retries > 0:
            logger.warning(f"API调用失败: {str(e)}，剩余重试次数: {max_retries-1}")
            return split_by_llm(text, model, max_word_count_english, max_retries-1)
        else:
            logger.error(f"API调用失败，无法拆分句子: {str(e)}")
            # 如果API调用失败，使用简单的句子拆分
            return text.split(". ")