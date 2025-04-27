# Captioner_Translate

基于 OpenAI API 的智能字幕翻译和优化工具。支持将英文字幕翻译成中文，并进行智能分段和优化处理。

## ✨ 特性

- 🎯 智能字幕处理
  - 支持 SRT 格式字幕文件的读取和生成
  - 自动生成双语 ASS 格式字幕
  - 智能处理逐字字幕，合并成完整句子
- 🔄 高级翻译功能

  - 支持上下文感知的智能翻译
  - 自动识别和保持专业术语的一致性
  - 可选的"反思模式"，提供更准确的翻译结果
  - 支持技术文档、教程等专业内容的翻译

- 🚀 性能优化

  - 多线程并行处理，提升翻译速度
  - 批量处理功能，支持多个字幕文件
  - 智能任务分配，避免 API 限流

- 📝 内容分析
  - 自动生成内容摘要
  - 提取关键术语和实体
  - 智能错误检测和修正

## 🚀 安装

1. 克隆项目

```bash
git clone https://github.com/yangping4271/Captioner_Translate.git
cd Captioner_Translate
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

1. 在项目根目录创建 `.env` 文件，配置以下参数：

```env
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=your_api_base_url
LLM_MODEL=gpt-4o-mini  # 或其他支持的模型
```

2. 可选配置参数（在 `subtitle_processor/config.py` 中）：

```python
target_language: str = "简体中文"  # 目标语言
thread_num: int = 18              # 并行处理线程数
batch_size: int = 20             # 批处理大小
max_word_count_english: int = 14  # 英文字幕最大字数
```

## 📖 使用方法

### 基本使用

1. 处理单个字幕文件：

```bash
python subtitle_translator_cli.py input.srt
```

2. 使用反思模式（更高质量）：

```bash
python subtitle_translator_cli.py input.srt -r
```

3. 指定不同的模型：

```bash
python subtitle_translator_cli.py input.srt -m gpt-4
```

### 批量处理

使用批处理脚本处理目录下的所有字幕：

```bash
./2translate.sh
```

### 输出文件

处理完成后会生成以下文件：

- `example_en.srt`: 优化后的英文字幕（句子已合并优化）
- `example_zh.srt`: 翻译后的中文字幕
- `example.ass`: 双语字幕文件（同时显示中英文）

## 高级功能

### 反思模式

使用 `-r` 参数启用反思模式，此模式会：

- 对初次翻译结果进行分析和改进
- 提供修改建议和原因
- 生成最终优化后的翻译

### 内容分析

系统会自动分析字幕内容并提供：

- 关键术语提取

### 智能分段

- 自动识别句子边界
- 考虑上下文语义
- 平衡字幕长度
- 优化显示时间

## 📝 注意事项

1. API 限制

- 请确保您的 API 密钥有足够的配额
- 建议使用 GPT-4 或同等级别的模型以获得最佳效果

2. 性能优化

- 调整 `thread_num` 和 `batch_size` 以适应您的 API 限制
- 对于长视频，建议分段处理

3. 最佳实践

- 处理前检查原始字幕质量
- 对于专业内容，建议使用反思模式
- 定期备份重要的字幕文件

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📝 许可证

本项目采用 MIT 许可证
