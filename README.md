# Captioner Translate

An intelligent subtitle translation tool powered by OpenAI API that translates English subtitles to Chinese and generates bilingual subtitle files.

> **📖 [中文文档 (Chinese Documentation)](README_zh.md)** | **English** (Current)

## ✨ Features

- 🎯 **Smart Subtitle Processing**: Supports SRT format, automatically generates bilingual ASS subtitles
- 🔄 **High-Quality Translation**: Context-aware translation with reflection mode for enhanced accuracy
- 🚀 **Efficient Processing**: Multi-threaded parallel processing with batch translation support
- 🌐 **Multiple API Support**: Compatible with OpenAI, OpenRouter, and other OpenAI-compatible APIs
- 📝 **Professional Output**: Generates properly formatted bilingual ASS files for video players

## 🚀 Quick Start

### Prerequisites

- Python 3.9 or higher
- OpenAI API key or compatible API service

### Installation

```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone the project
git clone https://github.com/yangping4271/Captioner_Translate.git
cd Captioner_Translate

# Install as a global tool
uv tool install .
```

### Configuration

Create a `.env` file in the project root with your API configuration:

```bash
# OpenAI API Configuration
OPENAI_API_KEY=your_api_key_here
OPENAI_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini

# Alternative: OpenRouter Configuration
# OPENAI_API_KEY=sk-or-v1-your_openrouter_key
# OPENAI_BASE_URL=https://openrouter.ai/api/v1
# LLM_MODEL=openai/gpt-4o-mini
```

### Basic Usage

After installation, you can use the `translate` command globally from any directory:

```bash
# Navigate to a directory containing .srt files, then translate
cd /path/to/your/subtitle/files
translate

# View all available options
translate --help
```

## 📁 File Processing Workflow

The tool automatically scans the current working directory and processes all `.srt` files:

1. **Discovery**: Scans current directory for `.srt` subtitle files
2. **Processing**:
   - Generates `_en.srt` (optimized English subtitles)
   - Generates `_zh.srt` (Chinese translations)
3. **Output**: Bilingual `.ass` subtitle files
4. **Cleanup**: Automatically removes intermediate files

### Supported File Patterns

- `filename.srt` → `filename_en.srt` + `filename_zh.srt` → `filename.ass`
- `filename_en.srt` → `filename_zh.srt` → `filename.ass`
- Files with existing `.ass` output are automatically skipped

## 🔧 Command Reference

### Main Command

- `translate`: Translate all subtitle files in the current working directory (available globally after installation)

### Options

- `-r, --reflect`: Enable reflection translation mode for higher quality
- `-m, --model TEXT`: Specify the LLM model to use
- `-d, --debug`: Enable debug logging for detailed processing information
- `--project-root PATH`: Path to Captioner_Translate project root
- `--version, -v`: Show version and exit

### Usage Examples

```bash
# Basic translation of all .srt files in current directory
translate

# Use reflection mode for higher quality translation
translate -r

# Use specific model (GPT-4)
translate -m gpt-4

# Enable debug output
translate -d

# Combine all options for maximum quality
translate -r -m gpt-4o -d
```

## 🏗️ Project Structure

```
captioner_translate/
├── captioner_translate/          # Main CLI package
│   ├── __init__.py
│   ├── cli.py                   # Typer-based CLI interface
│   ├── core.py                  # Core translation logic
│   └── translator.py            # Translation module
├── subtitle_processor/          # Subtitle processing modules
│   ├── __init__.py
│   ├── config.py               # Configuration management
│   ├── data.py                 # Data structures
│   ├── optimizer.py            # Translation optimization
│   ├── prompts.py              # AI prompts
│   ├── split_by_llm.py         # LLM-based text splitting
│   ├── spliter.py              # Subtitle splitting
│   └── summarizer.py           # Content summarization
├── utils/                      # Utility modules
│   ├── __init__.py
│   ├── json_repair.py          # JSON parsing utilities
│   ├── logger.py               # Logging configuration
│   ├── srt2ass.py              # SRT to ASS converter
│   └── test_opanai.py          # API testing utilities
├── test_subtitles/             # Sample subtitle files
├── logs/                       # Application logs
├── .env                        # Environment configuration
├── pyproject.toml              # Project configuration
└── README.md                   # This file
```

## 🌐 API Compatibility

This tool is compatible with various OpenAI-compatible APIs:

- **OpenAI**: Official OpenAI API
- **OpenRouter**: Access to multiple models through one API
- **Custom Endpoints**: Any OpenAI-compatible API service

## 🐛 Troubleshooting

### Common Issues

- **API Key Issues**: Ensure your `.env` file is properly configured and the API key is valid
- **Model Not Found**: Check that the specified model is available through your API provider

### Debug Mode

Enable debug mode for detailed logging:
```bash
translate -d
```

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

