#!/usr/bin/env python3
"""CLI interface for claude-code-log."""

import logging
import sys
from pathlib import Path
from typing import Optional

import click

from .converter import (
    convert_jsonl_to,
    process_projects_hierarchy,
)
from .cache import (
    CacheManager,
    get_cache_db_path,
    get_library_version,
)


def get_default_projects_dir() -> Path:
    """Get the default Claude projects directory path."""
    return Path.home() / ".claude" / "projects"


def convert_project_path_to_claude_dir(
    input_path: Path, base_projects_dir: Optional[Path] = None
) -> Path:
    """Convert a project path to the corresponding directory in ~/.claude/projects/.

    Args:
        input_path: The project path to convert
        base_projects_dir: Optional base directory for Claude projects.
                          Defaults to ~/.claude/projects/
    """
    # Get the real path to resolve any symlinks
    real_path = input_path.resolve()

    # Convert the path to the expected format: replace slashes with hyphens
    path_parts = list(real_path.parts)

    # Handle platform-specific root components
    if path_parts[0] == "/":
        # Unix: Remove leading slash, then prepend with dash
        # e.g., ['/', 'Users', 'test'] -> ['Users', 'test'] -> '-Users-test'
        path_parts = path_parts[1:]
        claude_project_name = "-" + "-".join(path_parts)
    elif len(path_parts) > 0 and len(path_parts[0]) >= 2 and path_parts[0][1:2] == ":":
        # Windows: Strip backslash and colon from drive letter, keep empty string for double dash
        # e.g., ['E:\\', 'Workspace', 'src'] -> ['E', '', 'Workspace', 'src'] -> 'E--Workspace-src'
        path_parts[0] = path_parts[0].rstrip("\\").rstrip(":")
        path_parts.insert(
            1, ""
        )  # Insert empty string to create double dash after drive letter
        claude_project_name = "-".join(path_parts)
    else:
        # Fallback for other cases
        claude_project_name = "-" + "-".join(path_parts)

    # Construct the path in the projects directory
    projects_dir = base_projects_dir or get_default_projects_dir()
    claude_projects_dir = projects_dir / claude_project_name

    return claude_projects_dir


def _clear_caches(input_path: Path, all_projects: bool) -> None:
    """Clear cache directories for the specified path."""
    try:
        library_version = get_library_version()

        if all_projects:
            # Clear cache for all project directories
            click.echo("Clearing caches for all projects...")

            # Delete the SQLite cache database (respects CLAUDE_CODE_LOG_CACHE_PATH env var)
            cache_db = get_cache_db_path(input_path)
            if cache_db.exists():
                try:
                    cache_db.unlink()
                    click.echo(f"  Deleted SQLite cache database: {cache_db}")
                except Exception as e:
                    click.echo(f"  Warning: Failed to delete cache database: {e}")

            # Also clean up old JSON cache directories (migration cleanup)
            project_dirs = [
                d
                for d in input_path.iterdir()
                if d.is_dir() and list(d.glob("*.jsonl"))
            ]

            for project_dir in project_dirs:
                try:
                    # Clean up old JSON cache directory if it exists
                    old_cache_dir = project_dir / "cache"
                    if old_cache_dir.exists():
                        import shutil

                        shutil.rmtree(old_cache_dir)
                        click.echo(f"  Cleared old JSON cache for {project_dir.name}")
                except Exception as e:
                    click.echo(
                        f"  Warning: Failed to clear old cache for {project_dir.name}: {e}"
                    )

        elif input_path.is_dir():
            # Clear cache for single directory
            click.echo(f"Clearing cache for {input_path}...")
            cache_manager = CacheManager(input_path, library_version)
            cache_manager.clear_cache()

            # Also clean up old JSON cache directory if it exists
            old_cache_dir = input_path / "cache"
            if old_cache_dir.exists():
                import shutil

                shutil.rmtree(old_cache_dir)
                click.echo("  Cleared old JSON cache directory")
        else:
            # Single file - no cache to clear
            click.echo("Cache clearing not applicable for single files.")

    except Exception as e:
        click.echo(f"Warning: Failed to clear cache: {e}")


def _clear_html_files(input_path: Path, all_projects: bool) -> None:
    """Clear generated HTML files for the specified path."""
    try:
        if all_projects:
            click.echo("Clearing HTML files for all projects...")
            project_dirs = [
                d
                for d in input_path.iterdir()
                if d.is_dir() and list(d.glob("*.jsonl"))
            ]

            total_removed = 0
            for project_dir in project_dirs:
                try:
                    output_files = list(project_dir.glob("*.html"))
                    for output_file in output_files:
                        output_file.unlink()
                        total_removed += 1

                    if output_files:
                        click.echo(
                            f"  Removed {len(output_files)} HTML files from {project_dir.name}"
                        )
                except Exception as e:
                    click.echo(
                        f"  Warning: Failed to clear HTML files for {project_dir.name}: {e}"
                    )

            # Also remove top-level index file
            index_file = input_path / "index.html"
            if index_file.exists():
                index_file.unlink()
                total_removed += 1
                click.echo("  Removed top-level index.html")

            if total_removed > 0:
                click.echo(f"Total: Removed {total_removed} HTML files")
            else:
                click.echo("No HTML files found to remove")

        elif input_path.is_dir():
            click.echo(f"Clearing HTML files for {input_path}...")
            output_files = list(input_path.glob("*.html"))
            for output_file in output_files:
                output_file.unlink()

            if output_files:
                click.echo(f"Removed {len(output_files)} HTML files")
            else:
                click.echo("No HTML files found to remove")
        else:
            output_file = input_path.with_suffix(".html")
            if output_file.exists():
                output_file.unlink()
                click.echo(f"Removed {output_file}")
            else:
                click.echo("No corresponding HTML file found to remove")

    except Exception as e:
        click.echo(f"Warning: Failed to clear HTML files: {e}")


@click.command()
@click.argument("input_path", type=click.Path(path_type=Path), required=False)
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path),
    help="Output file path (default: input file with .html extension, or combined_transcripts.html for directories)",
)
@click.option(
    "--open-browser",
    is_flag=True,
    help="Open the generated HTML file in the default browser",
)
@click.option(
    "--from-date",
    type=str,
    help='Filter messages from this date/time (e.g., "2 hours ago", "yesterday", "2025-06-08")',
)
@click.option(
    "--to-date",
    type=str,
    help='Filter messages up to this date/time (e.g., "1 hour ago", "today", "2025-06-08 15:00")',
)
@click.option(
    "--all-projects",
    is_flag=True,
    help="Process all projects in ~/.claude/projects/ hierarchy and create linked HTML files",
)
@click.option(
    "--no-individual-sessions",
    is_flag=True,
    help="Skip generating individual session HTML files (only create combined transcript)",
)
@click.option(
    "--skip-combined",
    is_flag=True,
    default=True,
    hidden=True,
    help="Skip generating combined transcript; create a project-level session index instead (now the default)",
)
@click.option(
    "--no-cache",
    is_flag=True,
    help="Disable caching and force reprocessing of all files",
)
@click.option(
    "--clear-cache",
    is_flag=True,
    help="Clear all cache directories before processing",
)
@click.option(
    "--clear-output",
    "--clear-html",
    "clear_output",
    is_flag=True,
    help="Clear generated HTML files and force regeneration",
)
@click.option(
    "--projects-dir",
    type=click.Path(path_type=Path, exists=False),
    default=None,
    help="Custom projects directory (default: ~/.claude/projects/). Useful for testing.",
)
@click.option(
    "--page-size",
    type=int,
    default=2000,
    help="Maximum messages per page for combined transcript (default: 2000). Sessions are never split across pages.",
)
@click.option(
    "--show-stats",
    is_flag=True,
    default=False,
    help="Show token usage statistics in generated output (hidden by default)",
)
@click.option(
    "--debug",
    is_flag=True,
    default=False,
    help="Show full traceback on errors.",
)
def main(
    input_path: Optional[Path],
    output: Optional[Path],
    open_browser: bool,
    from_date: Optional[str],
    to_date: Optional[str],
    all_projects: bool,
    no_individual_sessions: bool,
    skip_combined: bool,
    no_cache: bool,
    clear_cache: bool,
    clear_output: bool,
    projects_dir: Optional[Path],
    show_stats: bool,
    page_size: int,
    debug: bool,
) -> None:
    """Convert Claude transcript JSONL files to HTML.

    INPUT_PATH: Path to a Claude transcript JSONL file, directory containing JSONL files, or project path to convert. If not provided, defaults to ~/.claude/projects/ and --all-projects is used.
    """
    # Configure logging to show warnings and above
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

    try:
        # Handle default case - process all projects hierarchy if no input path
        if input_path is None:
            input_path = projects_dir or get_default_projects_dir()
            all_projects = True

        # Handle cache clearing
        if clear_cache:
            _clear_caches(input_path, all_projects)
            if clear_cache and not (from_date or to_date or input_path.is_file()):
                click.echo("Cache cleared successfully.")
                return

        # Handle output files clearing
        if clear_output:
            _clear_html_files(input_path, all_projects)
            if clear_output and not (from_date or to_date or input_path.is_file()):
                click.echo("HTML files cleared successfully.")
                return

        # Handle --all-projects flag or default behavior
        if all_projects:
            if not input_path.exists():
                raise FileNotFoundError(f"Projects directory not found: {input_path}")

            click.echo(f"Processing all projects in {input_path}...")
            output_path = process_projects_hierarchy(
                input_path,
                from_date,
                to_date,
                not no_cache,
                not no_individual_sessions,
                "html",
                None,
                page_size=page_size,
                skip_combined=skip_combined,
                show_stats=show_stats,
            )

            # Count processed projects
            project_count = len(
                [
                    d
                    for d in input_path.iterdir()
                    if d.is_dir() and list(d.glob("*.jsonl"))
                ]
            )
            click.echo(
                f"Successfully processed {project_count} projects and created index at {output_path}"
            )

            if open_browser:
                click.launch(str(output_path))
            return

        # Original single file/directory processing logic
        should_convert = False

        if not input_path.exists():
            should_convert = True
        elif input_path.is_dir():
            jsonl_files = list(input_path.glob("*.jsonl"))
            if len(jsonl_files) == 0:
                should_convert = True

        if should_convert:
            claude_path = convert_project_path_to_claude_dir(input_path, projects_dir)
            if claude_path.exists():
                click.echo(f"Converting project path {input_path} to {claude_path}")
                input_path = claude_path
            elif not input_path.exists():
                raise FileNotFoundError(
                    f"Neither {input_path} nor {claude_path} exists"
                )

        output_path = convert_jsonl_to(
            "html",
            input_path,
            output,
            from_date,
            to_date,
            not no_individual_sessions,
            not no_cache,
            image_export_mode=None,
            page_size=page_size,
            skip_combined=skip_combined,
            show_stats=show_stats,
        )
        if input_path.is_file():
            click.echo(f"Successfully converted {input_path} to {output_path}")
        else:
            jsonl_count = len(list(input_path.glob("*.jsonl")))
            if not no_individual_sessions:
                session_files = list(input_path.glob("session-*.html"))
                click.echo(
                    f"Successfully combined {jsonl_count} transcript files from {input_path} to {output_path} and generated {len(session_files)} individual session files"
                )
            else:
                click.echo(
                    f"Successfully combined {jsonl_count} transcript files from {input_path} to {output_path}"
                )

        if open_browser:
            click.launch(str(output_path))

    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        if debug:
            import traceback

            traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error converting file: {e}", err=True)
        if debug:
            import traceback

            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
