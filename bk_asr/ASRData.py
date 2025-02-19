import re
from typing import List
from pathlib import Path

class ASRDataSeg:
    def __init__(self, text: str, start_time: int, end_time: int):
        self.text = text
        self.start_time = start_time
        self.end_time = end_time

    def to_srt_ts(self) -> str:
        """Convert to SRT timestamp format"""
        return f"{self._ms_to_srt_time(self.start_time)} --> {self._ms_to_srt_time(self.end_time)}"

    @staticmethod
    def _ms_to_srt_time(ms: int) -> str:
        """Convert milliseconds to SRT time format (HH:MM:SS,mmm)"""
        total_seconds, milliseconds = divmod(ms, 1000)
        minutes, seconds = divmod(total_seconds, 60)
        hours, minutes = divmod(minutes, 60)
        return f"{int(hours):02}:{int(minutes):02}:{int(seconds):02},{int(milliseconds):03}"

    @property
    def transcript(self) -> str:
        """Return segment text"""
        return self.text

    def __str__(self) -> str:
        return f"ASRDataSeg({self.text}, {self.start_time}, {self.end_time})"


class ASRData:
    def __init__(self, segments: List[ASRDataSeg]):
        # 去除 segments.text 为空的
        filtered_segments = [seg for seg in segments if seg.text and seg.text.strip()]
        filtered_segments.sort(key=lambda x: x.start_time)
        self.segments = filtered_segments

    def __iter__(self):
        return iter(self.segments)
    
    def __len__(self) -> int:
        return len(self.segments)
    
    def has_data(self) -> bool:
        """Check if there are any utterances"""
        return len(self.segments) > 0
    
    def is_word_timestamp(self) -> bool:
        """
        判断是否是字级时间戳
        规则：
        1. 对于英文，每个segment应该只包含一个单词
        2. 对于中文，每个segment应该只包含一个汉字
        3. 允许20%的误差率
        """
        if not self.segments:
            return False
            
        valid_segments = 0
        total_segments = len(self.segments)
        
        for seg in self.segments:
            text = seg.text.strip()
            # 检查是否只包含一个英文单词或一个汉字
            if (len(text.split()) == 1 and text.isascii()) or len(text.strip()) <= 4:
                valid_segments += 1
        return (valid_segments / total_segments) >= 0.8

    def save(self, save_path: str) -> None:
        """Save the ASRData to a file"""
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        if save_path.endswith('.srt'):
            self.to_srt(save_path=save_path)
        else:
            raise ValueError(f"仅支持srt格式: {save_path}")

    def to_txt(self) -> str:
        """Convert to plain text"""
        return "\n".join(seg.transcript for seg in self.segments)

    def to_srt(self, save_path=None) -> str:
        """Convert to SRT subtitle format"""
        srt_lines = []
        for n, seg in enumerate(self.segments, 1):
            srt_lines.append(f"{n}\n{seg.to_srt_ts()}\n{seg.transcript}\n")

        srt_text = "\n".join(srt_lines)
        if save_path:
            with open(save_path, 'w', encoding='utf-8') as f:
                f.write(srt_text)
        return srt_text

    def to_json(self) -> dict:
        result_json = {}
        for i, segment in enumerate(self.segments, 1):
            # 检查是否有换行符
            if "\n" in segment.text:
                original_subtitle, translated_subtitle = segment.text.split("\n", 1)
            else:
                original_subtitle, translated_subtitle = segment.text, ""

            result_json[str(i)] = {
                "start_time": segment.start_time,
                "end_time": segment.end_time,
                "original_subtitle": original_subtitle,
                "translated_subtitle": translated_subtitle
            }
        return result_json

    def merge_segments(self, start_index: int, end_index: int, merged_text: str = None):
        """合并从 start_index 到 end_index 的段（包含）。"""
        if start_index < 0 or end_index >= len(self.segments) or start_index > end_index:
            raise IndexError("无效的段索引。")
        merged_start_time = self.segments[start_index].start_time
        merged_end_time = self.segments[end_index].end_time
        if merged_text is None:
            merged_text = ''.join(seg.text for seg in self.segments[start_index:end_index+1])
        merged_seg = ASRDataSeg(merged_text, merged_start_time, merged_end_time)
        # 替换 segments[start_index:end_index+1] 为 merged_seg
        self.segments[start_index:end_index+1] = [merged_seg]

    def merge_with_next_segment(self, index: int) -> None:
        """合并指定索引的段与下一个段。"""
        if index < 0 or index >= len(self.segments) - 1:
            raise IndexError("索引超出范围或没有下一个段可合并。")
        current_seg = self.segments[index]
        next_seg = self.segments[index + 1]
        merged_text = f"{current_seg.text} {next_seg.text}"
        merged_seg = ASRDataSeg(merged_text, current_seg.start_time, next_seg.end_time)
        self.segments[index] = merged_seg
        # 删除下一个段
        del self.segments[index + 1]

    def __str__(self):
        return self.to_txt()
    

def from_subtitle_file(file_path: str) -> 'ASRData':
    """从文件路径加载ASRData实例
    
    Args:
        file_path: 字幕文件路径，支持.srt格式
        
    Returns:
        ASRData: 解析后的ASRData实例
        
    Raises:
        ValueError: 不支持的文件格式或文件读取错误
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")
        
    try:
        content = file_path.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        content = file_path.read_text(encoding='gbk')
        
    suffix = file_path.suffix.lower()
    
    if suffix == '.srt':
        return from_srt(content)
    else:
        raise ValueError(f"仅支持srt格式: {suffix}")

def from_srt(srt_str: str) -> 'ASRData':
    """
    从SRT格式的字符串创建ASRData实例。

    :param srt_str: 包含SRT格式字幕的字符串。
    :return: 解析后的ASRData实例。
    """
    segments = []
    srt_time_pattern = re.compile(
        r'(\d{2}):(\d{2}):(\d{1,2})[.,](\d{3})\s-->\s(\d{2}):(\d{2}):(\d{1,2})[.,](\d{3})'
    )
    blocks = re.split(r'\n\s*\n', srt_str.strip())

    # 如果超过90%的块都超过4行，说明可能包含翻译文本
    blocks_lines_count = [len(block.splitlines()) for block in blocks]
    if all(count <= 4 for count in blocks_lines_count) and sum(count == 4 for count in blocks_lines_count) / len(blocks_lines_count) > 0.9:
        has_translated_subtitle = True
    else:
        has_translated_subtitle = False

    for block in blocks:
        lines = block.splitlines()
        if len(lines) < 3:
            continue

        match = srt_time_pattern.match(lines[1])
        if not match:
            continue

        time_parts = list(map(int, match.groups()))
        start_time = sum([
            time_parts[0] * 3600000,
            time_parts[1] * 60000,
            time_parts[2] * 1000,
            time_parts[3]
        ])
        end_time = sum([
            time_parts[4] * 3600000,
            time_parts[5] * 60000,
            time_parts[6] * 1000,
            time_parts[7]
        ])

        if has_translated_subtitle:
            text = '\n'.join(lines[2:]).strip()
        else:
            text = ' '.join(lines[2:])

        segments.append(ASRDataSeg(text, start_time, end_time))

    return ASRData(segments)