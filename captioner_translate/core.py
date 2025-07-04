"""
Core translation logic converted from the shell script.
"""

import os
import sys
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple
import glob
import re
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()


class TranslationError(Exception):
    """Custom exception for translation errors"""
    pass


class SubtitleTranslator:
    """Main class that handles the subtitle translation workflow"""
    
    def __init__(self, project_root: Optional[Path] = None):
        """
        Initialize the translator
        
        Args:
            project_root: Path to the Captioner_Translate project root
        """
        if project_root is None:
            # Try to find the project root
            project_root = self._find_project_root()
        
        self.project_root = Path(project_root)
        self.use_uv = self._check_uv_availability()
        
        if not self.project_root.exists():
            raise TranslationError(f"Project root not found: {self.project_root}")
    
    def _find_project_root(self) -> Path:
        """Find the Captioner_Translate project root"""
        # First try the home directory
        home_path = Path.home() / "Captioner_Translate"
        if home_path.exists() and (home_path / "pyproject.toml").exists():
            return home_path
        
        # Then try current directory and parents
        current = Path.cwd()
        while current != current.parent:
            if (current / "pyproject.toml").exists() and (current / "captioner_translate").exists():
                return current
            current = current.parent
        
        # Default fallback
        return Path.home() / "Captioner_Translate"
    
    def _check_uv_availability(self) -> bool:
        """Check if uv is available and project has pyproject.toml"""
        try:
            subprocess.run(["uv", "--version"], capture_output=True, check=True)
            return (self.project_root / "pyproject.toml").exists()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def discover_files(self, directory: Path) -> List[str]:
        """
        Discover subtitle files to process
        
        Args:
            directory: Directory to search for subtitle files
            
        Returns:
            List of base filenames (without extensions) to process
        """
        directory = Path(directory)
        
        # Find English subtitle files
        en_files = []
        for file in directory.glob("*_en.srt"):
            base_name = file.stem[:-3]  # Remove _en suffix
            en_files.append(base_name)
        
        # Find regular subtitle files (excluding _en.srt and _zh.srt)
        regular_files = []
        for file in directory.glob("*.srt"):
            if not (file.stem.endswith("_en") or file.stem.endswith("_zh")):
                regular_files.append(file.stem)
        
        # Combine and deduplicate, maintaining natural sort order
        all_files = sorted(set(en_files + regular_files), key=self._natural_sort_key)
        
        if not all_files:
            console.print("[yellow]No subtitle files found to translate.[/yellow]")
            return []
        
        return all_files
    
    def _natural_sort_key(self, text: str) -> List:
        """Natural sorting key for filenames with numbers"""
        return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', text)]
    
    def should_skip_file(self, base_name: str, directory: Path) -> Tuple[bool, str]:
        """
        Check if a file should be skipped
        
        Args:
            base_name: Base filename without extension
            directory: Directory containing the files
            
        Returns:
            Tuple of (should_skip, reason)
        """
        directory = Path(directory)
        ass_file = directory / f"{base_name}.ass"
        zh_file = directory / f"{base_name}_zh.srt"
        en_file = directory / f"{base_name}_en.srt"
        
        # Skip if .ass file already exists
        if ass_file.exists():
            return True, f"{base_name}.ass already exists"
        
        # If both zh and en exist, can generate ass directly
        if zh_file.exists() and en_file.exists():
            return False, "ready_for_ass_generation"
        
        return False, "needs_translation"
    
    def determine_input_file(self, base_name: str, directory: Path) -> Optional[Path]:
        """
        Determine which input file to use for translation
        
        Args:
            base_name: Base filename without extension
            directory: Directory containing the files
            
        Returns:
            Path to input file or None if no suitable file found
        """
        directory = Path(directory)
        zh_file = directory / f"{base_name}_zh.srt"
        en_file = directory / f"{base_name}_en.srt"
        original_file = directory / f"{base_name}.srt"
        
        # If zh exists but no en, need to translate original
        if zh_file.exists() and not en_file.exists():
            if original_file.exists():
                return original_file
            else:
                console.print(f"[red]ERROR: No original subtitle found for {base_name} with zh.srt[/red]")
                return None
        
        # If en exists, use it for translation
        elif en_file.exists():
            return en_file
        
        # If only original exists, use it
        elif original_file.exists():
            return original_file
        
        else:
            console.print(f"[red]ERROR: No input file found for {base_name}[/red]")
            return None
    
    def run_python_script(self, script_name: str, args: List[str], cwd: Optional[Path] = None) -> bool:
        """
        Run a Python script using either uv or virtual environment
        
        Args:
            script_name: Name of the Python script
            args: Arguments to pass to the script
            cwd: Working directory for the command
            
        Returns:
            True if successful, False otherwise
        """
        if cwd is None:
            cwd = Path.cwd()
        
        try:
            if self.use_uv:
                # Use uv run from project root
                cmd = ["uv", "run", script_name] + args
                result = subprocess.run(
                    cmd,
                    cwd=self.project_root,
                    capture_output=True,
                    text=True
                )
            else:
                # Use virtual environment
                venv_python = self.project_root / ".venv" / "bin" / "python3"
                script_path = self.project_root / script_name
                cmd = [str(venv_python), str(script_path)] + args
                result = subprocess.run(
                    cmd,
                    cwd=cwd,
                    capture_output=True,
                    text=True
                )
            
            if result.returncode != 0:
                console.print(f"[red]Error running {script_name}:[/red]")
                console.print(f"[red]{result.stderr}[/red]")
                return False
            
            return True
            
        except Exception as e:
            console.print(f"[red]Exception running {script_name}: {e}[/red]")
            return False
    
    def translate_file(self, input_file: Path, translator_args: List[str]) -> bool:
        """
        Translate a single subtitle file
        
        Args:
            input_file: Path to input subtitle file
            translator_args: Additional arguments for the translator
            
        Returns:
            True if successful, False otherwise
        """
        args = [str(input_file)] + translator_args
        return self.run_python_script("captioner_translate/translator.py", args)
    
    def generate_ass_file(self, base_name: str, directory: Path) -> bool:
        """
        Generate ASS file from zh and en subtitle files
        
        Args:
            base_name: Base filename without extension
            directory: Directory containing the files
            
        Returns:
            True if successful, False otherwise
        """
        directory = Path(directory)
        zh_file = directory / f"{base_name}_zh.srt"
        en_file = directory / f"{base_name}_en.srt"
        ass_file = directory / f"{base_name}.ass"
        
        if not (zh_file.exists() and en_file.exists()):
            return False
        
        # Prepare arguments for srt2ass.py
        if self.use_uv:
            args = [str(zh_file), str(en_file)]
        else:
            args = [str(zh_file), str(en_file)]
        
        success = self.run_python_script("utils/srt2ass.py", args, cwd=directory)
        
        if success and ass_file.exists():
            console.print(f"[green]INFO: {base_name}.ass done.[/green]")
            # Clean up intermediate files
            try:
                zh_file.unlink()
                en_file.unlink()
            except Exception as e:
                console.print(f"[yellow]Warning: Could not clean up intermediate files: {e}[/yellow]")
            return True
        
        return False

    def translate_directory(self, directory: Path, max_count: int = -1, translator_args: Optional[List[str]] = None) -> int:
        """
        Translate all subtitle files in a directory

        Args:
            directory: Directory containing subtitle files
            max_count: Maximum number of files to process (-1 for unlimited)
            translator_args: Additional arguments for the translator

        Returns:
            Number of files processed
        """
        if translator_args is None:
            translator_args = []

        directory = Path(directory)
        if not directory.exists():
            raise TranslationError(f"Directory not found: {directory}")

        # Discover files to process
        files = self.discover_files(directory)
        if not files:
            return 0

        console.print("[blue]Translation starting...[/blue]")

        if self.use_uv:
            console.print("[green]Using uv for Python execution...[/green]")
        else:
            console.print("[green]Using virtual environment for Python execution...[/green]")

        processed_count = 0

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:

            for file_base in files:
                # Check if we've reached the limit
                if max_count != -1 and processed_count >= max_count:
                    console.print(f"[yellow]Reached maximum execution limit ({max_count})[/yellow]")
                    break

                task = progress.add_task(f"Processing {file_base}...", total=None)

                # Check if file should be skipped
                should_skip, reason = self.should_skip_file(file_base, directory)

                if should_skip:
                    console.print(f"[yellow]INFO: {reason}[/yellow]")
                    progress.remove_task(task)
                    continue

                # Handle case where both zh and en exist - generate ass directly
                if reason == "ready_for_ass_generation":
                    progress.update(task, description=f"Generating ASS for {file_base}...")
                    self.generate_ass_file(file_base, directory)
                    progress.remove_task(task)
                    continue

                # Determine input file for translation
                input_file = self.determine_input_file(file_base, directory)
                if input_file is None:
                    progress.remove_task(task)
                    continue

                # Perform translation
                progress.update(task, description=f"Translating {file_base}...")
                console.print(f"\n[bold blue]=================== Translating {file_base} ===================[/bold blue]\n")

                success = self.translate_file(input_file, translator_args)
                if not success:
                    console.print(f"[red]Failed to translate {file_base}[/red]")
                    progress.remove_task(task)
                    continue

                processed_count += 1

                # Generate ASS file if both zh and en now exist
                progress.update(task, description=f"Generating ASS for {file_base}...")
                zh_file = directory / f"{file_base}_zh.srt"
                en_file = directory / f"{file_base}_en.srt"

                if zh_file.exists() and en_file.exists():
                    self.generate_ass_file(file_base, directory)

                progress.remove_task(task)

        console.print(f"[green]Translation completed. Processed {processed_count} files.[/green]")
        return processed_count

    def translate_single_file(self, file_path: Path, translator_args: Optional[List[str]] = None) -> int:
        """
        Translate a single subtitle file

        Args:
            file_path: Path to the subtitle file
            translator_args: Additional arguments for the translator

        Returns:
            Number of files processed (0 or 1)
        """
        if translator_args is None:
            translator_args = []

        file_path = Path(file_path)
        if not file_path.exists():
            raise TranslationError(f"File not found: {file_path}")

        if not file_path.suffix.lower() == '.srt':
            raise TranslationError(f"File must be a .srt subtitle file: {file_path}")

        directory = file_path.parent
        base_name = file_path.stem

        # Remove _en or _zh suffix if present
        if base_name.endswith('_en'):
            base_name = base_name[:-3]
        elif base_name.endswith('_zh'):
            base_name = base_name[:-3]

        console.print("[blue]Translation starting...[/blue]")

        if self.use_uv:
            console.print("[green]Using uv for Python execution...[/green]")
        else:
            console.print("[green]Using virtual environment for Python execution...[/green]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:

            task = progress.add_task(f"Processing {base_name}...", total=None)

            # Check if file should be skipped
            should_skip, reason = self.should_skip_file(base_name, directory)

            if should_skip:
                console.print(f"[yellow]INFO: {reason}[/yellow]")
                progress.remove_task(task)
                return 0

            # Handle case where both zh and en exist - generate ass directly
            if reason == "ready_for_ass_generation":
                progress.update(task, description=f"Generating ASS for {base_name}...")
                self.generate_ass_file(base_name, directory)
                progress.remove_task(task)
                return 1

            # Perform translation
            progress.update(task, description=f"Translating {base_name}...")
            console.print(f"\n[bold blue]=================== Translating {base_name} ===================[/bold blue]\n")

            success = self.translate_file(file_path, translator_args)
            if not success:
                console.print(f"[red]Failed to translate {base_name}[/red]")
                progress.remove_task(task)
                return 0

            # Generate ASS file if both zh and en now exist
            progress.update(task, description=f"Generating ASS for {base_name}...")
            zh_file = directory / f"{base_name}_zh.srt"
            en_file = directory / f"{base_name}_en.srt"

            if zh_file.exists() and en_file.exists():
                self.generate_ass_file(base_name, directory)

            progress.remove_task(task)

        console.print(f"[green]Translation completed. Processed 1 file.[/green]")
        return 1
