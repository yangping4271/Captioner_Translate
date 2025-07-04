# Captioner Translate - Python CLI

This document describes the Python CLI version of the Captioner Translate tool, converted from the original shell script `2translate.sh`.

## Overview

The Python CLI version provides the same functionality as the original shell script but with a modern, user-friendly interface using the Typer framework. It can be installed globally using `uv tool install` and provides rich help text, progress indicators, and better error handling.

## Installation

### Global Installation (Recommended)

Install the tool globally using uv:

```bash
uv tool install .
```

This will install two commands:
- `captioner-translate` - The main command
- `2translate` - Alias for backward compatibility with the original script name

### Development Installation

For development, install dependencies and run from the project:

```bash
uv sync
uv run captioner-translate --help
```

## Usage

### Basic Commands

#### Translate Files

Translate all subtitle files in the current directory:
```bash
captioner-translate translate
# or
2translate translate
```

Translate files in a specific directory:
```bash
captioner-translate translate /path/to/subtitles
```

#### Discover Files

Preview which files would be processed without actually translating:
```bash
captioner-translate discover
captioner-translate discover /path/to/subtitles
```

### Options

#### Limit Number of Files (`-n`, `--max-count`)
Process only a specific number of files:
```bash
captioner-translate translate -n 5
2translate translate -n 3
```

#### Enable Reflection Mode (`-r`, `--reflect`)
Use reflection translation for higher quality:
```bash
captioner-translate translate -r
```

#### Specify Model (`-m`, `--model`)
Use a specific LLM model:
```bash
captioner-translate translate -m gpt-4
```

#### Debug Mode (`-d`, `--debug`)
Enable detailed logging:
```bash
captioner-translate translate -d
```

#### Custom Project Root (`--project-root`)
Specify the Captioner_Translate project root directory:
```bash
captioner-translate translate --project-root /path/to/project
```

### Examples

```bash
# Translate max 5 files with reflection and debug
captioner-translate translate -n 5 -r -d

# Use GPT-4 model for translation
captioner-translate translate -m gpt-4

# Translate files in specific directory with custom project root
captioner-translate translate /path/to/subs --project-root /path/to/project

# Preview files that would be processed
captioner-translate discover /path/to/subtitles
```

## Comparison with Original Shell Script

### Equivalent Commands

| Shell Script | Python CLI |
|-------------|------------|
| `./2translate.sh` | `captioner-translate translate` |
| `./2translate.sh -n 5` | `captioner-translate translate -n 5` |
| `./2translate.sh -r -m gpt-4` | `captioner-translate translate -r -m gpt-4` |

### New Features

1. **Rich UI**: Progress indicators, colored output, and formatted panels
2. **Discovery Command**: Preview files without processing
3. **Better Help**: Comprehensive help text with examples
4. **Global Installation**: Install once, use anywhere
5. **Error Handling**: Better error messages and graceful failure handling
6. **Validation**: Input validation with helpful error messages

### Preserved Functionality

- ✅ File discovery logic (finds .srt files, handles _en/_zh patterns)
- ✅ Translation workflow (calls subtitle_translator_cli.py)
- ✅ ASS file generation (calls srt2ass.py)
- ✅ File cleanup (removes intermediate _zh.srt and _en.srt files)
- ✅ UV/virtual environment detection and usage
- ✅ Maximum file count limiting (-n option)
- ✅ All translator arguments pass-through (-r, -m, -d)
- ✅ Natural sorting of filenames
- ✅ Skip logic for existing .ass files

## File Processing Logic

The tool follows the same logic as the original shell script:

1. **Discovery**: Find all .srt files, excluding _en.srt and _zh.srt, plus any _en.srt files
2. **Skip Check**: Skip files that already have .ass output
3. **Direct ASS Generation**: If both _zh.srt and _en.srt exist, generate .ass directly
4. **Translation**: Determine input file and translate using subtitle_translator_cli.py
5. **ASS Generation**: Create .ass file from _zh.srt and _en.srt
6. **Cleanup**: Remove intermediate subtitle files

## Architecture

```
captioner_translate/
├── __init__.py          # Package metadata
├── core.py              # Core translation logic (SubtitleTranslator class)
└── cli.py               # Typer CLI interface
```

### Key Classes

- `SubtitleTranslator`: Main class handling file discovery, translation workflow
- `TranslationError`: Custom exception for translation-related errors

### Dependencies

- `typer`: Modern CLI framework
- `rich`: Rich text and beautiful formatting
- `pathlib`: Path handling
- All original dependencies (openai, python-dotenv, etc.)

## Development

### Running Tests

```bash
# Test discovery
uv run captioner-translate discover test_subtitles

# Test translation (dry run)
uv run captioner-translate translate test_subtitles -n 1 -d
```

### Building and Installing

```bash
# Build the package
uv build

# Install globally
uv tool install .

# Uninstall
uv tool uninstall captioner-translate
```

## Migration from Shell Script

To migrate from the shell script to the Python CLI:

1. Install the Python CLI: `uv tool install .`
2. Replace `./2translate.sh` with `2translate translate` in your workflows
3. Use `captioner-translate discover` to preview files before processing
4. Enjoy the improved user experience with progress indicators and better error messages

The Python CLI maintains full backward compatibility with the shell script's functionality while providing a much better user experience.
