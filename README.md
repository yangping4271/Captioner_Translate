# Captioner_Translate

基于 OpenAI API 的智能字幕翻译和优化工具。支持将英文字幕翻译成中文，并进行智能分段和优化处理。

## ✨ 特性

- 🎯 支持 SRT 格式字幕文件
- 🔄 智能断句优化，避免过长或过短的字幕
- 🚀 多线程并行处理，提升翻译速度
- 📝 支持字幕内容总结
- 🎨 仅译文 srt 字幕或者双语 ass 字幕

## 🚀 安装

1. 克隆项目

```bash
git clone https://github.com/yourusername/VideoCaptioner.git
cd VideoCaptioner
```

2. 创建并激活虚拟环境

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
.\venv\Scripts\activate  # Windows
```

3. 安装依赖

```bash
pip install -r requirements.txt
```

## ⚙️ 配置

在项目根目录创建 `.env` 文件，配置以下参数：

```env
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=your_api_base_url
LLM_MODEL=gpt-3.5-turbo  # 或其他支持的模型
```

## 📖 使用方法

### 命令行使用

处理单个字幕文件：

```bash
python subtitle_translator_cli.py input.srt
```

批量处理字幕文件：

```bash
./2translate.sh
```

### 输出文件

- 原始字幕文件：`example.srt`
- 优化后的英文字幕：`example_en.srt`
- 翻译后的中文字幕：`example_zh.srt`
- 批处理后双语字幕：`example.ass`

## 🔧 参数配置

可以在 `subtitle_translator_cli.py` 中调整以下参数：

- `thread_num`: 并行处理线程数（默认：10）
- `batch_size`: 批处理大小（默认：20）
- `max_word_count_cjk`: 中文字幕最大字数（默认：18）
- `max_word_count_english`: 英文字幕最大字数（默认：12）

## 📝 许可证

本项目采用 MIT 许可证
