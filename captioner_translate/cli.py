"""
CLI interface for the Captioner Translate tool using Typer.
"""

import os
from pathlib import Path
from typing import Optional, Annotated
import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from .core import SubtitleTranslator, TranslationError

# Initialize console and app
console = Console()
# Create the main app without subcommands
app = typer.Typer(
    name="translate",
    help="Translate all subtitle files (.srt) in the current working directory",
    rich_markup_mode="rich",
    add_completion=False,
    no_args_is_help=False,
)

# Version callback
def version_callback(value: bool):
    if value:
        from . import __version__
        console.print(f"Captioner Translate version: {__version__}")
        raise typer.Exit()


@app.command()
def main(
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
    show_version: Annotated[
        Optional[bool],
        typer.Option("--version", "-v", callback=version_callback, help="Show version and exit")
    ] = None,
):
    """
    Translate all subtitle files (.srt) in the current working directory.

    This command automatically scans the current working directory for all subtitle
    files (.srt), translates them using OpenAI API, and generates bilingual ASS files
    with both English and Chinese subtitles.

    The tool handles various file naming patterns:
    - file.srt -> file_en.srt + file_zh.srt -> file.ass
    - file_en.srt -> file_zh.srt -> file.ass
    - Skips files that already have corresponding .ass output

    Examples:

        # Translate all subtitle files in current directory
        uv run translate

        # Use reflection mode for higher quality
        uv run translate -r

        # Use specific model and enable debug
        uv run translate -m gpt-4 -d

        # Translate with all options
        uv run translate -r -m gpt-4o -d
    """
    
    # Set debug environment variable if requested
    if debug:
        os.environ['DEBUG'] = 'true'

    # Use current working directory
    directory = Path.cwd()

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

        # Discover subtitle files in current directory
        files = translator.discover_files(directory)

        if not files:
            console.print(Panel(
                f"No subtitle files (.srt) found in current directory: {directory}",
                title="No Files Found",
                border_style="yellow"
            ))
            console.print("\n[yellow]Make sure you're in a directory containing .srt subtitle files.[/yellow]")
            return

        # Show startup information
        startup_info = Text()
        startup_info.append("🎬 Captioner Translate\n", style="bold blue")
        startup_info.append(f"📁 Directory: {directory}\n", style="cyan")
        startup_info.append(f"📄 Files found: {len(files)}\n", style="cyan")
        if reflect:
            startup_info.append("🔄 Reflection mode: enabled\n", style="green")
        if llm_model:
            startup_info.append(f"🤖 Model: {llm_model}\n", style="magenta")
        if debug:
            startup_info.append("🐛 Debug mode: enabled\n", style="red")

        console.print(Panel(startup_info, title="Configuration", border_style="blue"))

        # Show discovered files
        console.print(f"\n[bold blue]Found {len(files)} subtitle files:[/bold blue]")
        for file_base in files:
            should_skip, reason = translator.should_skip_file(file_base, directory)
            if should_skip:
                console.print(f"  [yellow]⏭️  {file_base}[/yellow] - {reason}")
            elif reason == "ready_for_ass_generation":
                console.print(f"  [green]🎬 {file_base}[/green] - ready for ASS generation")
            else:
                console.print(f"  [blue]📝 {file_base}[/blue] - needs translation")
        console.print()

        # Process all files
        processed_count = translator.translate_directory(
            directory=directory,
            max_count=-1,  # Process all files
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





if __name__ == "__main__":
    app()
