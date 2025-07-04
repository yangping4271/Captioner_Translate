# Captioner Translate

基于 OpenAI API 的智能字幕翻译工具，支持将英文字幕翻译成中文并生成双语字幕文件。

**📖 文档语言:**
- **[English Documentation](README.md)**
- **中文文档** (当前)

## ✨ 特性

- 🎯 **智能字幕处理**: 支持 SRT 格式，自动生成双语 ASS 字幕
- 🔄 **高质量翻译**: 上下文感知翻译，支持反思模式提升准确性
- 🚀 **高效处理**: 多线程并行处理，支持批量翻译
- 🌐 **多种 API 支持**: 兼容 OpenAI、OpenRouter 和其他 OpenAI 兼容的 API
- 📝 **专业输出**: 生成适用于视频播放器的格式化双语 ASS 文件

## 🚀 快速开始

### 前置要求

- Python 3.9 或更高版本
- OpenAI API 密钥或兼容的 API 服务

### 安装

```bash
# 如果还没有安装 uv，先安装 uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 克隆项目
git clone https://github.com/yangping4271/Captioner_Translate.git
cd Captioner_Translate

# 安装为全局工具
uv tool install .
```

### 配置

在项目根目录创建 `.env` 文件并配置 API：

```bash
# OpenAI API 配置
OPENAI_API_KEY=your_api_key_here
OPENAI_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini

# 或者使用 OpenRouter 配置
# OPENAI_API_KEY=sk-or-v1-your_openrouter_key
# OPENAI_BASE_URL=https://openrouter.ai/api/v1
# LLM_MODEL=openai/gpt-4o-mini
```

### 基本使用

安装完成后，您可以在任何目录中全局使用 `translate` 命令：

```bash
# 导航到包含 .srt 文件的目录，然后翻译
cd /path/to/your/subtitle/files
translate

# 查看所有可用选项
translate --help
```

## 📁 文件处理流程

工具自动扫描当前工作目录并处理所有 `.srt` 文件：

1. **发现**: 扫描当前目录中的 `.srt` 字幕文件
2. **处理**:
   - 生成 `_en.srt`（优化后的英文字幕）
   - 生成 `_zh.srt`（中文翻译）
3. **输出**: 双语 `.ass` 字幕文件
4. **清理**: 自动删除中间文件

### 支持的文件模式

- `filename.srt` → `filename_en.srt` + `filename_zh.srt` → `filename.ass`
- `filename_en.srt` → `filename_zh.srt` → `filename.ass`
- 已有 `.ass` 输出的文件会自动跳过

## 🔧 命令参考

### 主命令

- `translate`: 翻译当前工作目录中的所有字幕文件（安装后全局可用）

### 选项

- `-r, --reflect`: 启用反思翻译模式以获得更高质量
- `-m, --model TEXT`: 指定要使用的 LLM 模型
- `-d, --debug`: 启用调试日志以获得详细的处理信息
- `--project-root PATH`: Captioner_Translate 项目根目录路径
- `--version, -v`: 显示版本并退出

### 使用示例

```bash
# 翻译当前目录中所有 .srt 文件
translate

# 使用反思模式进行高质量翻译
translate -r

# 使用特定模型 (GPT-4)
translate -m gpt-4

# 启用调试输出
translate -d

# 组合所有选项以获得最高质量
translate -r -m gpt-4o -d
```

## 🏗️ 项目结构

```
captioner_translate/
├── captioner_translate/          # 主 CLI 包
│   ├── __init__.py
│   ├── cli.py                   # Typer CLI 接口
│   ├── core.py                  # 核心翻译逻辑
│   └── translator.py            # 翻译模块
├── subtitle_processor/          # 字幕处理模块
│   ├── __init__.py
│   ├── config.py               # 配置管理
│   ├── data.py                 # 数据结构
│   ├── optimizer.py            # 翻译优化
│   ├── prompts.py              # AI 提示词
│   ├── split_by_llm.py         # LLM 文本分割
│   ├── spliter.py              # 字幕分割
│   └── summarizer.py           # 内容摘要
├── utils/                      # 工具模块
│   ├── __init__.py
│   ├── json_repair.py          # JSON 解析工具
│   ├── logger.py               # 日志配置
│   ├── srt2ass.py              # SRT 到 ASS 转换器
│   └── test_opanai.py          # API 测试工具
├── test_subtitles/             # 示例字幕文件
├── logs/                       # 应用日志
├── .env                        # 环境配置
├── pyproject.toml              # 项目配置
├── README.md                   # 英文文档
└── README_zh.md                # 中文文档（本文件）
```

## 🌐 API 兼容性

本工具兼容多种 OpenAI 兼容的 API：

- **OpenAI**: 官方 OpenAI API
- **OpenRouter**: 通过一个 API 访问多个模型
- **自定义端点**: 任何 OpenAI 兼容的 API 服务

## 🐛 故障排除

### 常见问题

- **API 密钥问题**: 确保 `.env` 文件配置正确且 API 密钥有效
- **模型未找到**: 检查指定的模型是否通过您的 API 提供商可用

### 调试模式

启用调试模式以获得详细日志：
```bash
translate -d
```

## 📄 许可证

MIT 许可证 - 详见 [LICENSE](LICENSE) 文件。

## 🤝 贡献

欢迎贡献！请随时提交 Pull Request。

---

**📖 更多信息请参考 [English Documentation](README.md)**
