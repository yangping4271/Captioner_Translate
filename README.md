# Captioner_Translate

基于 OpenAI API 的智能字幕翻译工具，支持英文字幕翻译成中文，并生成双语字幕。

## ✨ 特性

- 🎯 **智能字幕处理**：支持 SRT 格式，自动生成双语 ASS 字幕
- 🔄 **高质量翻译**：上下文感知翻译，支持反思模式提升准确性
- 🚀 **高效处理**：多线程并行处理，支持批量翻译

## 🚀 快速开始

### 安装

**推荐使用 uv：**
```bash
# 安装 uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 克隆并设置项目
git clone https://github.com/yangping4271/Captioner_Translate.git
cd Captioner_Translate
uv sync
```

**传统方式：**
```bash
git clone https://github.com/yangping4271/Captioner_Translate.git
cd Captioner_Translate
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 配置

创建 `.env` 文件：
```env
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=your_api_base_url
LLM_MODEL=gpt-4o-mini
```

## 📖 使用方法

### 基本使用
```bash
# 使用 uv（推荐）
uv run python subtitle_translator_cli.py input.srt

# 传统方式
python subtitle_translator_cli.py input.srt
```

### 高质量翻译（反思模式）
```bash
uv run python subtitle_translator_cli.py input.srt -r
```

### 批量处理
```bash
./2translate.sh
```

### 生成双语字幕
```bash
uv run python srt2ass.py video_zh.srt video_en.srt
```

## 📁 输出文件

- `example_en.srt`: 优化后的英文字幕
- `example_zh.srt`: 翻译后的中文字幕  
- `example.ass`: 双语字幕文件

## ⚙️ 配置选项

在 `subtitle_processor/config.py` 中可调整：
- `target_language`: 目标语言（默认：简体中文）
- `thread_num`: 并行线程数（默认：18）
- `batch_size`: 批处理大小（默认：20）

## �� 许可证

MIT License
