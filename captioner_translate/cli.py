"""
CLI interface for the Captioner Translate tool using Typer.
"""

import os
import sys
from pathlib import Path
from typing import List, Optional, Annotated
import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from .core import SubtitleTranslator, TranslationError

# Initialize console and app
console = Console()
app = typer.Typer(
    name="captioner-translate",
    help="A subtitle translation tool using OpenAI API",
    rich_markup_mode="rich",
    add_completion=False,
)

# Version callback
def version_callback(value: bool):
    if value:
        from . import __version__
        console.print(f"Captioner Translate version: {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        Optional[bool], 
        typer.Option("--version", "-v", callback=version_callback, help="Show version and exit")
    ] = None,
):
    """
    Captioner Translate - A subtitle translation tool using OpenAI API
    
    This tool converts subtitle files (.srt) to bilingual ASS format with Chinese and English subtitles.
    It automatically discovers subtitle files in the current directory and processes them using OpenAI's API.
    """
    pass


@app.command()
def translate(
    directory: Annotated[
        Optional[Path], 
        typer.Argument(help="Directory containing subtitle files (default: current directory)")
    ] = None,
    max_count: Annotated[
        int, 
        typer.Option("-n", "--max-count", help="Maximum number of files to process (-1 for unlimited)")
    ] = -1,
    reflect: Annotated[
        bool, 
        typer.Option("-r", "--reflect", help="Enable reflection translation mode for higher quality")
    ] = False,
    llm_model: Annotated[
        Optional[str], 
        typer.Option("-m", "--model", help="Specify the LLM model to use")
    ] = None,
    debug: Annotated[
        bool, 
        typer.Option("-d", "--debug", help="Enable debug logging for detailed processing information")
    ] = False,
    project_root: Annotated[
        Optional[Path], 
        typer.Option("--project-root", help="Path to Captioner_Translate project root")
    ] = None,
):
    """
    Translate subtitle files in a directory.
    
    This command discovers all subtitle files (.srt) in the specified directory,
    translates them using OpenAI API, and generates bilingual ASS files.
    
    The tool handles various file naming patterns:
    - file.srt -> file_en.srt + file_zh.srt -> file.ass
    - file_en.srt -> file_zh.srt -> file.ass
    - Skips files that already have .ass output
    
    Examples:
    
        # Translate all files in current directory
        captioner-translate translate
        
        # Translate maximum 5 files with reflection mode
        captioner-translate translate -n 5 -r
        
        # Use specific model and enable debug
        captioner-translate translate -m gpt-4 -d
        
        # Translate files in specific directory
        captioner-translate translate /path/to/subtitles
    """
    
    # Set debug environment variable if requested
    if debug:
        os.environ['DEBUG'] = 'true'
    
    # Use current directory if none specified
    if directory is None:
        directory = Path.cwd()
    
    # Validate directory
    if not directory.exists():
        console.print(f"[red]Error: Directory not found: {directory}[/red]")
        raise typer.Exit(1)
    
    if not directory.is_dir():
        console.print(f"[red]Error: Path is not a directory: {directory}[/red]")
        raise typer.Exit(1)
    
    # Validate max_count
    if max_count < -1 or max_count == 0:
        console.print("[red]Error: -n parameter must be a positive integer or -1 for unlimited[/red]")
        raise typer.Exit(1)
    
    # Build translator arguments
    translator_args = []
    if reflect:
        translator_args.extend(["-r", "--reflect"])
    if llm_model:
        translator_args.extend(["-m", llm_model])
    if debug:
        translator_args.extend(["-d", "--debug"])
    
    try:
        # Initialize translator
        translator = SubtitleTranslator(project_root=project_root)
        
        # Show startup information
        startup_info = Text()
        startup_info.append("🎬 Captioner Translate\n", style="bold blue")
        startup_info.append(f"📁 Directory: {directory}\n", style="cyan")
        if max_count != -1:
            startup_info.append(f"🔢 Max files: {max_count}\n", style="yellow")
        if reflect:
            startup_info.append("🔄 Reflection mode: enabled\n", style="green")
        if llm_model:
            startup_info.append(f"🤖 Model: {llm_model}\n", style="magenta")
        if debug:
            startup_info.append("🐛 Debug mode: enabled\n", style="red")
        
        console.print(Panel(startup_info, title="Configuration", border_style="blue"))
        
        # Perform translation
        processed_count = translator.translate_directory(
            directory=directory,
            max_count=max_count,
            translator_args=translator_args
        )
        
        # Show completion summary
        if processed_count > 0:
            console.print(Panel(
                f"✅ Successfully processed {processed_count} files",
                title="Completed",
                border_style="green"
            ))
        else:
            console.print(Panel(
                "ℹ️ No files were processed",
                title="Information",
                border_style="yellow"
            ))
        
    except TranslationError as e:
        console.print(f"[red]Translation Error: {e}[/red]")
        raise typer.Exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Translation interrupted by user[/yellow]")
        raise typer.Exit(130)
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        if debug:
            import traceback
            console.print(traceback.format_exc())
        raise typer.Exit(1)


@app.command()
def discover(
    directory: Annotated[
        Optional[Path], 
        typer.Argument(help="Directory to search for subtitle files (default: current directory)")
    ] = None,
):
    """
    Discover and list subtitle files that would be processed.
    
    This command shows which subtitle files would be processed by the translate command
    without actually performing any translation. Useful for previewing what files
    will be affected.
    
    Examples:
    
        # Discover files in current directory
        captioner-translate discover
        
        # Discover files in specific directory
        captioner-translate discover /path/to/subtitles
    """
    
    # Use current directory if none specified
    if directory is None:
        directory = Path.cwd()
    
    # Validate directory
    if not directory.exists():
        console.print(f"[red]Error: Directory not found: {directory}[/red]")
        raise typer.Exit(1)
    
    if not directory.is_dir():
        console.print(f"[red]Error: Path is not a directory: {directory}[/red]")
        raise typer.Exit(1)
    
    try:
        # Initialize translator
        translator = SubtitleTranslator()
        
        # Discover files
        files = translator.discover_files(directory)
        
        if not files:
            console.print(Panel(
                "No subtitle files found to process",
                title="Discovery Results",
                border_style="yellow"
            ))
            return
        
        # Show discovered files with their status
        console.print(f"\n[bold blue]Found {len(files)} subtitle files in {directory}:[/bold blue]\n")
        
        for file_base in files:
            should_skip, reason = translator.should_skip_file(file_base, directory)
            
            if should_skip:
                console.print(f"  [yellow]⏭️  {file_base}[/yellow] - {reason}")
            elif reason == "ready_for_ass_generation":
                console.print(f"  [green]🎬 {file_base}[/green] - ready for ASS generation")
            else:
                console.print(f"  [blue]📝 {file_base}[/blue] - needs translation")
        
        console.print()
        
    except TranslationError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
