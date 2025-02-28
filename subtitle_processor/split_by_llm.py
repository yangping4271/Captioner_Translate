import re
from typing import List
from concurrent.futures import ThreadPoolExecutor, as_completed
from openai import OpenAI

from .data import SubtitleSegment
from .prompts import SPLIT_SYSTEM_PROMPT
from .config import SubtitleConfig, get_default_config
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
    logger.debug(f"分段文本: \n\n{text}\n")
    
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
        logger.debug(f"API返回结果: \n\n{result}\n")

        # 清理和分割文本 - 简化处理，保留原始格式
        result = re.sub(r'\n+', '', result)
        
        # 直接按<br>分割，保留原始格式和空格
        sentences = result.split("<br>")
        
        # 清理空白行，但保留内部空格
        sentences = [seg.strip() for seg in sentences if seg.strip()]

        # 验证句子长度
        new_sentences = []
        for sentence in sentences:
            threshold = max_word_count_english + 5
            word_count = count_words(sentence)
            
            if word_count > max_word_count_english:
                if word_count < threshold:
                    logger.debug(f"发现长句子, 长度为: {word_count}\n{sentence}\n")
                else:
                    logger.info(f"发现超长句子, 长度为: {word_count}\n{sentence}\n")
                    
                # 尝试切分句子
                split_results = split_by_common_words(sentence)
                new_sentences.extend(split_results)
            else:
                new_sentences.append(sentence)
        
        sentences = new_sentences

        # 验证结果
        word_count = count_words(text)
        expected_segments = word_count / max_word_count_english
        actual_segments = len(sentences)
        
        if actual_segments < expected_segments * 0.9:
            logger.warning(f"断句数量不足：预期 {expected_segments:.1f}，实际 {actual_segments}")
            
        return sentences
        
    except Exception as e:
        if max_retries > 0:
            logger.warning(f"API调用失败: {str(e)}，剩余重试次数: {max_retries-1}")
            return split_by_llm(text, model, max_word_count_english, max_retries-1)
        else:
            logger.error(f"API调用失败，无法拆分句子: {str(e)}")
            # 如果API调用失败，使用简单的句子拆分
            return text.split(". ")
        
def split_by_common_words(text: str) -> List[str]:
    """
    在常见连接词处对句子进行分割

    Args:
        text: 需要分割的句子
    Returns:
        分割后的句子列表，如果无法分割则返回包含原句子的列表
    """
    # 定义在词语前面分割的常见词
    prefix_split_words = {
        # 连接词和介词
        "and", "or", "but", "if", "then", "because", "as", "until",
        "while", "what", "when", "where", "nor", "yet", "so", "for",
        "however", "moreover", "furthermore", "additionally", "besides",
        "therefore", "thus", "hence", "consequently",
        # 从句引导词
        "that", "which", "who", "whom", "whose", "why", "how",
        # 时间和条件
        "before", "after", "since", "while", "unless", "although",
        "though", "even though", "whereas", "whether",
        # 目的和结果
        "in order to", "so that", "such that", "in case", "provided that",
        # 对比和让步
        "despite", "in spite of", "rather than", "instead of",
        # 补充和递进
        "also", "besides", "in addition", "moreover", "furthermore",
        "similarly", "likewise", "meanwhile", "subsequently"
    }

    # 定义在词语后面分割的常见词
    suffix_split_words = {
        # 标点符号
        ".", ",", "!", "?", ":", ";", "...", "…",
        # 引号和括号
        "\"", "'", "'", "'", """, """, ")", "]", "}",
        # 常见结尾词和短语
        "too", "indeed", "instead", "anyway", "however",
        "therefore", "hence", "thus", "accordingly",
        # 时间和地点结尾
        "now", "then", "here", "there", "today", "tonight",
        "tomorrow", "yesterday",
        # 语气和强调
        "really", "actually", "certainly", "definitely", "absolutely",
        "obviously", "clearly", "precisely", "exactly",
        # 总结和过渡
        "finally", "lastly", "ultimately", "eventually", "altogether",
        "overall", "generally", "basically", "essentially"
    }

    # 预处理文本
    text = text.strip()
    words = text.split()
    
    # 如果句子太短，直接返回
    if len(words) < 8:
        return [text]
        
    # 寻找分割点
    split_positions = []
    for i, word in enumerate(words):
        word_lower = word.lower().strip(",.!?")
        # 检查前缀分割词
        if i > 2 and i < len(words) - 2:  # 确保不在句子开头和结尾太近的位置
            # 检查单词和短语
            for prefix in prefix_split_words:
                if " " in prefix:  # 处理多词短语
                    if i + len(prefix.split()) <= len(words):
                        phrase = " ".join(words[i:i+len(prefix.split())]).lower()
                        if phrase == prefix:
                            split_positions.append(i)
                            break
                elif word_lower == prefix:  # 处理单个词
                    split_positions.append(i)
                    break
        
        # 检查后缀分割词
        if i > 2 and i < len(words) - 1:  # 确保不在句子开头太近的位置
            if word_lower in suffix_split_words:
                split_positions.append(i + 1)  # 在后缀词之后分割
    
    # 如果没找到合适的分割点，返回原句子
    if not split_positions:
        return [text]
    
    # 排序并去重分割点
    split_positions = sorted(list(set(split_positions)))
    
    # 执行分割
    result = []
    start = 0
    for pos in split_positions:
        if pos - start >= 3:  # 确保每个分段至少有3个词
            segment = " ".join(words[start:pos])
            if segment:
                result.append(segment)
            start = pos
    
    # 添加最后一个分段
    if start < len(words):
        last_segment = " ".join(words[start:])
        if last_segment:
            result.append(last_segment)
    
    # 如果分割结果不理想（没有分段或只有一个分段），返回原句子
    if len(result) <= 1:
        return [text]

    # 如果有多于两个分段，尝试合并最短的相邻分段
    while len(result) > 2:
        # 找出最短的相邻分段对
        min_length = float('inf')
        merge_index = 0
        
        for i in range(len(result) - 1):
            current_len = count_words(result[i]) + count_words(result[i + 1])
            if current_len < min_length:
                min_length = current_len
                merge_index = i
        
        # 合并找到的最短相邻分段
        merged_segment = result[merge_index] + " " + result[merge_index + 1]
        result = result[:merge_index] + [merged_segment] + result[merge_index + 2:]

    # 最终检查两个分段是否合理
    if any(count_words(segment) < 3 for segment in result):
        return [text]
    
    # 检查分段是否平衡（差距不要太大）
    lengths = [count_words(segment) for segment in result]
    if max(lengths) > min(lengths) * 3:  # 如果最长的分段超过最短的3倍
        return [text]
    logger.debug(f"优化分割: \t{text}:\t{'--'.join(result)}\n")
    return result