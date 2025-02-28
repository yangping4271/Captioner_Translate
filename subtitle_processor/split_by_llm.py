import re
from typing import List
from concurrent.futures import ThreadPoolExecutor, as_completed
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

def split_long_sentence(client: OpenAI, model: str, sentence: str, max_word_count_english: int) -> List[str]:
    """
    使用LLM拆分过长的句子
    
    Args:
        client: OpenAI客户端
        sentence: 要拆分的句子
        max_word_count_english: 英文最大单词数
        
    Returns:
        List[str]: 拆分后的句子列表
    """
    logger.info(f"开始处理超长句子，长度为: {count_words(sentence)}\n句子内容: {sentence[:100]}...")
    
    user_prompt = f"""Please split this sentence into smaller parts. Each part should be no longer than {max_word_count_english} words. 
    Keep the meaning intact and maintain proper grammar. Split only where it makes sense semantically:
    
    {sentence}"""
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2,
            timeout=30
        )
        
        result = response.choices[0].message.content
        # 按换行符分割，清理空白
        sub_segments = [seg.strip() for seg in result.split("\n") if seg.strip()]
        
        # 记录拆分结果
        logger.info(f"句子拆分完成，拆分为 {len(sub_segments)} 个子句")
        for i, seg in enumerate(sub_segments, 1):
            logger.debug(f"子句 {i}/{len(sub_segments)}, 长度: {count_words(seg)}\n内容: {seg}")
            
        return sub_segments
        
    except Exception as e:
        logger.error(f"拆分长句子失败: {str(e)}\n原句: {sentence[:100]}...")
        # 如果失败，返回原句子
        return [sentence]

def split_long_sentences_parallel(client: OpenAI, 
                                model: str,
                                long_segments: List[str], 
                                max_word_count_english: int,
                                max_workers: int = 5) -> List[str]:
    """
    并行处理多个超长句子
    
    Args:
        client: OpenAI客户端
        long_segments: 需要处理的超长句子列表
        max_word_count_english: 英文最大单词数
        max_workers: 最大线程数
        
    Returns:
        List[str]: 所有拆分后的句子列表
    """
    logger.info(f"开始并行处理 {len(long_segments)} 个超长句子，使用 {max_workers} 个线程")
    results = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 创建future到原始索引的映射
        future_to_index = {
            executor.submit(split_long_sentence, client, model, segment, max_word_count_english): i
            for i, segment in enumerate(long_segments)
        }
        
        completed = 0
        # 按完成顺序获取结果
        for future in as_completed(future_to_index):
            index = future_to_index[future]
            completed += 1
            try:
                sub_segments = future.result()
                results.append((index, sub_segments))
                logger.info(f"完成第 {completed}/{len(long_segments)} 个句子的处理，原始索引: {index}")
            except Exception as e:
                logger.error(f"处理第 {completed}/{len(long_segments)} 个句子失败 (索引: {index}): {str(e)}")
                # 如果处理失败，保留原句子
                results.append((index, [long_segments[index]]))
    
    # 按原始顺序排序结果
    results.sort(key=lambda x: x[0])
    # 展平结果列表
    final_results = [segment for _, segments in results for segment in segments]
    logger.info(f"所有超长句子处理完成，共处理 {len(long_segments)} 个句子，拆分为 {len(final_results)} 个子句")
    return final_results

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
        segments = result.split("<br>")
        
        # 清理空白行，但保留内部空格
        segments = [seg.strip() for seg in segments if seg.strip()]

        # 验证句子长度
        final_segments = []
        long_segments = []
        long_segment_indices = []
        
        for i, segment in enumerate(segments, 1):
            threshold = max_word_count_english + 5
            if max_word_count_english < count_words(segment) < threshold:
                logger.debug(f"发现长句子 (第{i}句), 长度为: {count_words(segment)}\n{segment}\n")
            if count_words(segment) > threshold:
                logger.info(f"发现超长句子 (第{i}句), 长度为: {count_words(segment)}\n{segment}\n")
                long_segments.append(segment)
                long_segment_indices.append(i)
            else:
                final_segments.append(segment)
        
        # 如果有超长句子，使用多线程处理
        if long_segments:
            logger.info(f"共发现 {len(long_segments)} 个超长句子需要处理")
            split_results = split_long_sentences_parallel(client, model, long_segments, max_word_count_english)
            
            # 将拆分结果插入到原来的位置
            for i, idx in enumerate(long_segment_indices):
                final_segments.insert(idx, split_results[i])
                logger.debug(f"将第 {i+1}/{len(long_segments)} 个拆分结果插入到原始位置 {idx}")
        
        segments = final_segments

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