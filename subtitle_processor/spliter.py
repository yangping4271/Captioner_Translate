import difflib
import re
from concurrent.futures import ThreadPoolExecutor
from typing import List

from subtitle_processor.split_by_llm import split_by_llm
from subtitle_processor.data import SubtitleData, SubtitleSegment
from subtitle_processor.config import get_default_config
from utils.logger import setup_logger

logger = setup_logger("subtitle_spliter")

SEGMENT_THRESHOLD = 500  # 每个分段的最大字数
FIXED_NUM_THREADS = 1  # 固定的线程数量
SPLIT_RANGE = 30  # 在分割点前后寻找最大时间间隔的范围
MAX_GAP = 1500  # 允许每个词语之间的最大时间间隔 ms

class SubtitleProcessError(Exception):
    """字幕处理相关的异常"""
    pass

def is_pure_punctuation(s: str) -> bool:
    """
    检查字符串是否仅由标点符号组成
    """
    return not re.search(r'\w', s, flags=re.UNICODE)


def count_words(text: str) -> int:
    """
    统计多语言文本中的字符/单词数
    支持:
    - 英文（按空格分词）
    - CJK文字（中日韩统一表意文字）
    - 韩文/谚文
    - 泰文
    - 阿拉伯文
    - 俄文西里尔字母
    - 希伯来文
    - 越南文
    每个字符都计为1个单位，英文按照空格分词计数
    """
    # 定义各种语言的Unicode范围
    patterns = [
        r'[\u4e00-\u9fff]',           # 中日韩统一表意文字
        r'[\u3040-\u309f]',           # 平假名
        r'[\u30a0-\u30ff]',           # 片假名
        r'[\uac00-\ud7af]',           # 韩文音节
        r'[\u0e00-\u0e7f]',           # 泰文
        r'[\u0600-\u06ff]',           # 阿拉伯文
        r'[\u0400-\u04ff]',           # 西里尔字母（俄文等）
        r'[\u0590-\u05ff]',           # 希伯来文
        r'[\u1e00-\u1eff]',           # 越南文
        r'[\u3130-\u318f]',           # 韩文兼容字母
    ]
    
    # 统计所有非英文字符
    non_english_chars = 0
    remaining_text = text
    
    for pattern in patterns:
        # 计算当前语言的字符数
        chars = len(re.findall(pattern, remaining_text))
        non_english_chars += chars
        # 从文本中移除已计数的字符
        remaining_text = re.sub(pattern, ' ', remaining_text)
    
    # 计算英文单词数（处理剩余的文本）
    english_words = len(remaining_text.strip().split())
    
    return non_english_chars + english_words


def preprocess_text(s: str) -> str:
    """
    通过转换为小写并规范化空格来标准化文本
    """
    return ' '.join(s.lower().split())


def merge_segments_based_on_sentences(segments: List[SubtitleSegment], sentences: List[str], max_unmatched: int = 5) -> List[SubtitleSegment]:
    """
    基于提供的句子列表合并字幕分段
    
    Args:
        segments: 字幕段列表
        sentences: 句子列表
        max_unmatched: 允许的最大未匹配句子数量，超过此数量将抛出异常
        
    Returns:
        合并后的 SubtitleSegment 列表
        
    Raises:
        SubtitleProcessError: 当未匹配句子数量超过阈值时抛出
    """
    asr_texts = [seg.text for seg in segments]
    asr_len = len(asr_texts)
    asr_index = 0  # 当前分段索引位置
    threshold = 0.5  # 相似度阈值
    max_shift = 30  # 滑动窗口的最大偏移量
    unmatched_count = 0  # 未匹配句子计数

    new_segments = []

    for sentence in sentences:
        # 保留原始句子，不做任何处理
        original_sentence = sentence
        sentence_proc = preprocess_text(sentence)
        word_count = count_words(sentence_proc)
        best_ratio = 0.0
        best_pos = None
        best_window_size = 0

        # 滑动窗口大小，优先考虑接近句子词数的窗口
        max_window_size = min(word_count * 2, asr_len - asr_index)
        min_window_size = max(1, word_count // 2)
        window_sizes = sorted(range(min_window_size, max_window_size + 1), key=lambda x: abs(x - word_count))

        for window_size in window_sizes:
            max_start = min(asr_index + max_shift + 1, asr_len - window_size + 1)
            for start in range(asr_index, max_start):
                substr = ''.join(asr_texts[start:start + window_size])
                substr_proc = preprocess_text(substr)
                ratio = difflib.SequenceMatcher(None, sentence_proc, substr_proc).ratio()

                if ratio > best_ratio:
                    best_ratio = ratio
                    best_pos = start
                    best_window_size = window_size
                if ratio == 1.0:
                    break  # 完全匹配
            if best_ratio == 1.0:
                break  # 完全匹配

        if best_ratio >= threshold and best_pos is not None:
            start_seg_index = best_pos
            end_seg_index = best_pos + best_window_size - 1
            
            segs_to_merge = segments[start_seg_index:end_seg_index + 1]

            # 按照时间切分避免合并跨度大的
            seg_groups = merge_by_time_gaps(segs_to_merge, max_gap=MAX_GAP)

            for group in seg_groups:
                # 直接使用LLM返回的原始句子，完全保留格式和标点
                merged_text = original_sentence
                
                merged_start_time = group[0].start_time
                merged_end_time = group[-1].end_time
                merged_seg = SubtitleSegment(merged_text, merged_start_time, merged_end_time)
                
                # 直接添加合并后的段落，不进行额外的拆分
                new_segments.append(merged_seg)
            
            max_shift = 30
            asr_index = end_seg_index + 1  # 移动到下一个未处理的分段
        else:
            logger.warning(f"无法匹配句子: {sentence}")
            unmatched_count += 1
            if unmatched_count > max_unmatched:
                logger.error(f"未匹配句子数量超过阈值 ({max_unmatched})，返回原始分段")
                return segments
            max_shift = 100
            asr_index = min(asr_index + 1, asr_len - 1)  # 确保不会超出范围
    
    # 如果没有成功匹配任何句子，返回原始分段
    if not new_segments:
        logger.warning("没有成功匹配任何句子，返回原始分段")
        return segments

    return new_segments


def split_long_segment(segs_to_merge: List[SubtitleSegment]) -> List[SubtitleSegment]:
    """
    基于最大时间间隔拆分长分段，根据文本类型使用不同的最大词数限制
    """
    result_segs = []
    
    # 添加空列表检查
    if not segs_to_merge:
        return result_segs
        
    # 修改合并文本的方式，添加空格
    merged_text = ' '.join(seg.text.strip() for seg in segs_to_merge)

    # 根据文本类型确定最大词数限制
    config = get_default_config()
    max_word_count = config.max_word_count_english

    # 基本情况：如果分段足够短或无法进一步拆分
    if count_words(merged_text) <= max_word_count or len(segs_to_merge) == 1:
        # 保留原始文本格式，不添加额外标点符号
        merged_seg = SubtitleSegment(
            merged_text.strip(),
            segs_to_merge[0].start_time,
            segs_to_merge[-1].end_time
        )
        result_segs.append(merged_seg)
        return result_segs

    # 检查时间间隔是否都相等
    n = len(segs_to_merge)
    gaps = [segs_to_merge[i+1].start_time - segs_to_merge[i].end_time for i in range(n-1)]
    all_equal = all(abs(gap - gaps[0]) < 1e-6 for gap in gaps)

    if all_equal:
        # 如果时间间隔都相等，在中间位置断句
        split_index = n // 2
    else:
        # 在分段中间2/3部分寻找最大时间间隔点
        start_idx = n // 6
        end_idx = (5 * n) // 6
        split_index = max(
            range(start_idx, end_idx),
            key=lambda i: segs_to_merge[i + 1].start_time - segs_to_merge[i].end_time,
            default=n // 2
        )

    # 尝试在句子边界拆分
    # 检查拆分点前后的文本是否有句子结束标志
    sentence_end_markers = ['.', '!', '?', '。', '！', '？']
    
    # 向前搜索最近的句子结束点
    for i in range(split_index, -1, -1):
        if any(marker in segs_to_merge[i].text for marker in sentence_end_markers):
            split_index = i
            break
    
    first_segs = segs_to_merge[:split_index + 1]
    second_segs = segs_to_merge[split_index + 1:]
    
    # 递归拆分
    result_segs.extend(split_long_segment(first_segs))
    result_segs.extend(split_long_segment(second_segs))

    return result_segs


def split_asr_data(asr_data: SubtitleData, num_segments: int) -> List[SubtitleData]:
    """
    将字幕数据分割成指定数量的段，确保分段时考虑字数限制和句子完整性
    """
    total_segs = len(asr_data.segments)
    total_word_count = count_words(asr_data.to_txt())
    words_per_segment = total_word_count // num_segments

    if num_segments <= 1 or total_segs <= num_segments:
        return [asr_data]

    # 获取所有段落的累计字数
    cumulative_words = [0]
    for i in range(total_segs):
        words = count_words(asr_data.segments[i].text)
        cumulative_words.append(cumulative_words[-1] + words)
    
    # 定义句子结束标志
    sentence_end_markers = ['.', '!', '?', '。', '！', '？', '…']
    
    # 定义不应结束于此的词语
    bad_end_words = ["and", "or", "but", "so", "yet", "for", "nor", "in", "on", "at", "to", "with", "by", "as"]
    
    # 计算分割点
    split_indices = []
    for i in range(1, num_segments):
        target_words = i * words_per_segment
        
        # 找到最接近目标字数的分段索引
        seg_index = 0
        for j in range(total_segs):
            if cumulative_words[j+1] >= target_words:
                seg_index = j
                break
        
        # 搜索范围：向前和向后各30个分段
        search_range = 30
        start_idx = max(0, seg_index - search_range)
        end_idx = min(total_segs - 1, seg_index + search_range)
        
        # 寻找最佳分割点
        best_index = seg_index
        best_score = -1  # 分数越高越好
        
        for j in range(start_idx, end_idx + 1):
            # 跳过已经选择的分割点
            if j in split_indices:
                continue
                
            # 计算与目标字数的接近程度 (负数分数，越接近0越好)
            words_score = -abs(cumulative_words[j+1] - target_words) / 100
            
            # 检查是否在句子结束处 (加分)
            ends_with_sentence = False
            current_text = asr_data.segments[j].text.strip().lower()
            for marker in sentence_end_markers:
                if marker in current_text:
                    ends_with_sentence = True
                    break
            
            # 检查是否以不好的词结尾 (减分)
            ends_with_bad_word = False
            for word in bad_end_words:
                if current_text.endswith(word) or current_text.endswith(word + " "):
                    ends_with_bad_word = True
                    break
            
            # 检查时间间隔 (加分)
            time_gap = 0
            if j < total_segs - 1:
                time_gap = asr_data.segments[j+1].start_time - asr_data.segments[j].end_time
            
            # 计算总分
            score = words_score
            if ends_with_sentence:
                score += 10  # 句子结束加10分
            if ends_with_bad_word:
                score -= 20  # 以不好的词结尾减20分
            score += time_gap / 1000  # 时间间隔按秒加分
            
            # 更新最佳索引
            if score > best_score:
                best_score = score
                best_index = j
                
            # 如果找到完美的结束点，直接使用它
            if ends_with_sentence and not ends_with_bad_word and abs(cumulative_words[j+1] - target_words) < 100:
                best_index = j
                break
        
        # 检查所选分割点是否合适
        current_text = asr_data.segments[best_index].text.strip().lower()
        next_text = "" if best_index + 1 >= total_segs else asr_data.segments[best_index + 1].text.strip().lower()
        
        # 如果该分割点结束于不好的词或者是短语的中间，尝试向前找更好的句子结束点
        if any(current_text.endswith(word) for word in bad_end_words):
            # 向前搜索更好的分割点
            for j in range(best_index - 1, start_idx - 1, -1):
                prev_text = asr_data.segments[j].text.strip().lower()
                if any(marker in prev_text for marker in sentence_end_markers) and not any(prev_text.endswith(word) for word in bad_end_words):
                    best_index = j
                    break
        
        split_indices.append(best_index)
    
    # 移除重复的分割点
    split_indices = sorted(list(set(split_indices)))
    
    # 根据分割点拆分ASRData
    segments = []
    prev_index = 0
    for index in split_indices:
        part = SubtitleData(asr_data.segments[prev_index:index + 1])
        segments.append(part)
        prev_index = index + 1
    
    # 添加最后一部分
    if prev_index < total_segs:
        part = SubtitleData(asr_data.segments[prev_index:])
        segments.append(part)
    
    return segments


def merge_short_segment(segments: List[SubtitleSegment]) -> None:
    """
    合并过短的分段
    """
    if not segments:  # 添加空列表检查
        return
        
    i = 0  # 从头开始遍历
    while i < len(segments) - 1:  # 修改遍历方式
        current_seg = segments[i]
        next_seg = segments[i + 1]
        
        # 判断是否需要合并:
        # 1. 时间间隔小于300ms
        # 2. 当前段落或下一段落词数小于5
        # 3. 合并后总词数不超过限制
        time_gap = abs(next_seg.start_time - current_seg.end_time)
        current_words = count_words(current_seg.text)
        next_words = count_words(next_seg.text)
        total_words = current_words + next_words
        config = get_default_config()
        max_word_count = config.max_word_count_english

        if time_gap < 300 and (current_words < 5 or next_words <= 5) \
            and total_words <= max_word_count \
            and ("." not in current_seg.text and "?" not in current_seg.text and "!" not in current_seg.text):
            # 执行合并操作
            logger.info(f"合并优化: {current_seg.text} --- {next_seg.text}")
            # 更新当前段落的文本和结束时间
            current_seg.text += " " + next_seg.text
            current_seg.end_time = next_seg.end_time
            
            # 从列表中移除下一个段落
            segments.pop(i + 1)
            # 不增加i，因为需要继续检查合并后的段落
        else:
            i += 1


def determine_num_segments(word_count: int, threshold: int = 1000) -> int:
    """
    根据字数计算分段数，每1000个字为一个分段，至少为1
    """
    num_segments = word_count // threshold
    # 如果存在余数，增加一个分段
    if word_count % threshold > 0:
        num_segments += 1
    return max(1, num_segments)


def preprocess_segments(segments: List[SubtitleSegment], need_lower=False) -> List[SubtitleSegment]:
    """
    预处理字幕分段:
    1. 移除纯标点符号的分段
    2. 保留原始大小写格式
    
    Args:
        segments: 字幕分段列表
        need_lower: 是否需要转换为小写（默认为False，保留原始大小写）
    Returns:
        处理后的分段列表
    """
    new_segments = []
    for seg in segments:
        if not is_pure_punctuation(seg.text):
            # 保留原始格式，不转换为小写
            new_segments.append(seg)
    return new_segments


def merge_by_time_gaps(segments: List[SubtitleSegment], max_gap: int = MAX_GAP, check_large_gaps: bool = False) -> List[List[SubtitleSegment]]:
    """
    根据时间间隔合并分段
    """
    if not segments:
        return []
    
    result = []
    current_group = [segments[0]]
    recent_gaps = []  # 存储最近的时间间隔
    WINDOW_SIZE = 5   # 检查最近5个间隔
    
    for i in range(1, len(segments)):
        time_gap = segments[i].start_time - segments[i-1].end_time
        
        if check_large_gaps:
            recent_gaps.append(time_gap)
            if len(recent_gaps) > WINDOW_SIZE:
                recent_gaps.pop(0)
            if len(recent_gaps) == WINDOW_SIZE:
                avg_gap = sum(recent_gaps) / len(recent_gaps)
                # 如果当前间隔大于平均值的3倍
                if time_gap > avg_gap*3 and len(current_group) > 5:
                    result.append(current_group)
                    current_group = []
                    recent_gaps = []  # 重置间隔记录
        
        if time_gap > max_gap:
            result.append(current_group)
            current_group = []
            recent_gaps = []  # 重置间隔记录
            
        current_group.append(segments[i])
    
    if current_group:
        result.append(current_group)
    
    return result


def process_by_llm(segments: List[SubtitleSegment], 
                   model: str = "gpt-4o-mini",
                   max_word_count_english: int = None) -> List[SubtitleSegment]:
    """
    使用LLM处理分段
    
    Args:
        segments: 字幕分段列表
        model: 使用的语言模型
        max_word_count_english: 英文最大单词数
        
    Returns:
        List[SubtitleSegment]: 处理后的字幕分段列表
    """
    config = get_default_config()
    max_word_count_english = max_word_count_english or config.max_word_count_english
        
    # 修改合并文本的方式，添加空格
    txt = " ".join([seg.text.strip() for seg in segments])
    # 使用LLM拆分句子
    sentences = split_by_llm(txt, 
                           model=model, 
                           max_word_count_english=max_word_count_english)
    logger.info(f"分段的句子提取完成，共 {len(sentences)} 句")
    # 对当前分段进行合并处理
    merged_segments = merge_segments_based_on_sentences(segments, sentences)
    return merged_segments


def merge_segments(asr_data: SubtitleData, 
                   model: str = "gpt-4o-mini", 
                   num_threads: int = FIXED_NUM_THREADS, 
                   max_word_count_english: int = None,
                   save_split: str = None) -> SubtitleData:
    """
    合并字幕分段
    
    Args:
        asr_data: 字幕数据
        model: 使用的语言模型
        num_threads: 线程数量
        max_word_count_english: 英文最大单词数
        save_split: 保存断句结果的文件路径
    """
    # 使用配置中的值
    config = get_default_config()
    max_word_count_english = max_word_count_english or config.max_word_count_english

    # 预处理字幕数据，移除纯标点符号的分段，并处理仅包含字母和撇号的文本
    asr_data.segments = preprocess_segments(asr_data.segments, need_lower=False)
    txt = asr_data.to_txt().replace("\n", " ").strip()  # 将换行符替换为空格而不是直接删除
    total_word_count = count_words(txt)

    # 确定分段数，分割字幕数据
    num_segments = determine_num_segments(total_word_count, threshold=SEGMENT_THRESHOLD)
    logger.info(f"根据字数 {total_word_count}，分段字数限制{SEGMENT_THRESHOLD}, 确定分段数: {num_segments}")
    asr_data_segments = split_asr_data(asr_data, num_segments)

    # 多线程处理每个分段
    logger.info("开始并行处理每个分段...")
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        def process_segment(asr_data_part):
            try:
                return process_by_llm(asr_data_part.segments, model=model)
            except Exception as e:
                raise Exception(f"LLM处理失败: {str(e)}")

        # 并行处理所有分段
        processed_segments = list(executor.map(process_segment, asr_data_segments))

    # 合并所有处理后的分段
    final_segments = []
    for segment in processed_segments:
        final_segments.extend(segment)

    final_segments.sort(key=lambda seg: seg.start_time)

    # 如果需要保存断句结果
    if save_split:
        try:
            # 获取所有文本
            all_text = asr_data.to_txt()
            # 获取所有处理后的分段文本
            all_segments = [seg.text for seg in final_segments]
            
            # 显示断句结果
            logger.info(f"所有分段断句完成，共 {len(all_segments)} 句")
            for i, segment in enumerate(all_segments, 1):
                logger.debug(f"第 {i} 句: {segment}")
                if count_words(segment) > max_word_count_english:
                    logger.info(f"第 {i} 句长度超过限制,长度为: {count_words(segment)}\n{segment}")
            
            # 保存结果
            # from .data import save_split_results
            # save_split_results(all_text, all_segments, save_split)

        except Exception as e:
            logger.error(f"保存断句结果失败: {str(e)}")

    merge_short_segment(final_segments)

    # 创建最终的字幕数据对象
    final_asr_data = SubtitleData(final_segments)
    return final_asr_data