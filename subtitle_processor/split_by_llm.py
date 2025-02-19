import re
from typing import List

from openai import OpenAI
import retry

from .prompts import SPLIT_SYSTEM_PROMPT
from .config import SubtitleConfig
from utils.logger import setup_logger

logger = setup_logger("subtitle_spliter")

def count_words(text: str) -> int:
    """
    统计混合文本中英文单词数和中文字符数的总和
    
    Args:
        text: 输入文本，可以包含中英文
        
    Returns:
        int: 中文字符数与英文单词数的总和
    """
    logger.debug(f"开始统计文本字数，文本长度：{len(text)}")
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    english_text = re.sub(r'[\u4e00-\u9fff]', ' ', text)
    english_words = len(english_text.strip().split())
    total = english_words + chinese_chars
    logger.debug(f"字数统计结果：中文字符 {chinese_chars}，英文单词 {english_words}，总计 {total}")
    return total


def split_by_llm(text: str, 
                 model: str = None, 
                 max_word_count_cjk: int = None,
                 max_word_count_english: int = None) -> List[str]:
    """
    包装 split_by_llm_retry 函数，确保在重试全部失败后返回原文本
    
    Args:
        text: 要分段的文本
        model: 使用的LLM模型，如果为None则使用配置中的默认值
        max_word_count_cjk: 中文最大字数，如果为None则使用配置中的默认值
        max_word_count_english: 英文最大单词数，如果为None则使用配置中的默认值
        
    Returns:
        List[str]: 分段后的文本列表
    """
    config = SubtitleConfig()
    model = model or config.llm_model
    max_word_count_cjk = max_word_count_cjk or config.max_word_count_cjk
    max_word_count_english = max_word_count_english or config.max_word_count_english
    
    logger.debug(f"开始文本分段处理：模型 {model}，中文限制 {max_word_count_cjk}，英文限制 {max_word_count_english}")
    
    try:
        return split_by_llm_retry(text, model, max_word_count_cjk, max_word_count_english)
    except Exception as e:
        logger.error(f"文本分段失败，将返回原文本: {str(e)}")
        return [text]

@retry.retry(tries=2)
def split_by_llm_retry(text: str, 
                      model: str,
                      max_word_count_cjk: int,
                      max_word_count_english: int) -> List[str]:
    """
    使用LLM进行文本断句
    
    Args:
        text: 要分段的文本
        model: 使用的LLM模型
        max_word_count_cjk: 中文最大字数
        max_word_count_english: 英文最大单词数
        
    Returns:
        List[str]: 分段后的文本列表
        
    Raises:
        Exception: 当分段结果不满足要求时抛出异常
    """
    logger.debug(f"开始处理文本，长度：{len(text)}，模型：{model}")
    
    # 准备提示词
    system_prompt = SPLIT_SYSTEM_PROMPT.replace("[max_word_count_cjk]", str(max_word_count_cjk))
    system_prompt = system_prompt.replace("[max_word_count_english]", str(max_word_count_english))
    user_prompt = f"Please use multiple <br> tags to separate the following sentence:\n{text}"
    
    # 初始化客户端
    config = SubtitleConfig()
    client = OpenAI(
        base_url=config.openai_base_url,
        api_key=config.openai_api_key
    )
    
    try:
        # 调用API
        logger.debug("正在调用OpenAI API...")
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2,
            timeout=80
        )
        
        # 处理返回结果
        result = response.choices[0].message.content
        logger.debug(f"API返回原始结果: {result}")
        
        # 清理和分割文本
        result = re.sub(r'\n+', '', result)
        split_result = [segment.strip() for segment in result.split("<br>") if segment.strip()]
        
        # 验证结果
        word_count = count_words(text)
        expected_segments = word_count / max_word_count_cjk
        actual_segments = len(split_result)
        logger.info(f"断句完成：预期段数 {expected_segments:.1f}，实际段数 {actual_segments}")
        
        if actual_segments < expected_segments * 0.9:
            raise Exception(f"断句数量不足：预期 {expected_segments:.1f}，实际 {actual_segments}")
        
        # 记录每个分段的详细信息
        for i, segment in enumerate(split_result, 1):
            seg_words = count_words(segment)
            logger.debug(f"第{i}段：长度 {len(segment)}，字数 {seg_words}")
            
        return split_result
        
    except Exception as e:
        logger.error(f"断句处理失败: {str(e)}")
        raise