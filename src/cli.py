"""Command-line interface for consolidate-bear-markdown."""

import argparse
import logging
import sys
import tomli
from pathlib import Path
from typing import Dict, Any
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from markitdown import MarkItDown  # type: ignore
from openai import OpenAI
from .file_system import FileSystem
from .logging_config import setup_logging
from .markdown_processor_v2 import MarkdownProcessorV2
from .markitdown_wrapper import MarkItDownWrapper

console = Console()
error_console = Console(stderr=True)


def load_config(config_path: str | Path) -> Dict[str, Any]:
    """Load configuration from TOML file.

    Args:
        config_path: Path to config file

    Returns:
        Configuration dictionary
    """
    try:
        with open(config_path, "rb") as f:
            return tomli.load(f)
    except Exception as e:
        error_console.print(f"[red]Error loading config file: {str(e)}[/red]")
        sys.exit(1)


def validate_config(config: Dict[str, Any]) -> None:
    """Validate configuration values.

    Args:
        config: Configuration dictionary

    Raises:
        ValueError: If configuration is invalid
    """
    required_fields = {
        "srcDir": "Source directory path",
        "destDir": "Destination directory path",
        "openai_key": "OpenAI API key",
    }

    for field, desc in required_fields.items():
        if field not in config:
            raise ValueError(f"Missing required config field: {field} ({desc})")

    # Validate log level if present
    if "logLevel" in config:
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR"}
        if config["logLevel"].upper() not in valid_levels:
            raise ValueError(
                f"Invalid log level: {config['logLevel']}. "
                f"Must be one of: {', '.join(valid_levels)}"
            )


def display_summary(stats: Dict[str, int]) -> None:
    """Display processing summary with rich formatting.

    Args:
        stats: Processing statistics dictionary with integer values
    """
    # Create summary table
    table = Table(title="Processing Summary", show_header=True)
    table.add_column("Category", style="cyan")
    table.add_column("Total", justify="right", style="white")
    table.add_column("Success", justify="right", style="green")
    table.add_column("Error", justify="right", style="red")
    table.add_column("Skipped", justify="right", style="yellow")

    # Add file statistics
    table.add_row(
        "Files",
        str(stats["files_processed"] + stats["files_errored"]),
        str(stats["files_processed"]),
        str(stats["files_errored"]),
        "N/A",
    )

    # Add attachment statistics
    total_attachments = (
        stats["success"]
        + stats["error"]
        + stats["missing"]
        + stats["skipped"]
    )
    table.add_row(
        "Attachments",
        str(total_attachments),
        str(stats["success"]),
        str(stats["error"]),
        str(stats["skipped"]),
    )

    # Display summary
    console.print()
    console.print(Panel(table, title="Processing Complete"))


def main() -> None:
    """Main entry point."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Process Bear.app markdown files and inline attachments."
    )
    parser.add_argument(
        "-c",
        "--config",
        required=True,
        help="Path to config.toml file",
    )
    args = parser.parse_args()

    try:
        # Load and validate configuration
        config = load_config(args.config)
        validate_config(config)

        # Convert paths to Path objects
        src_dir = Path(config["srcDir"]).expanduser()
        dest_dir = Path(config["destDir"]).expanduser()
        cbm_dir = Path(config.get("cbm_dir", ".cbm")).expanduser()

        # Set up logging
        setup_logging(
            log_level=config.get("logLevel", "INFO"),
            cbm_dir=str(cbm_dir),
        )
        logger = logging.getLogger(__name__)

        # Display startup banner
        console.print()
        console.print(
            Panel(
                "[cyan]Bear Markdown Processor[/cyan]\n"
                f"Source: [green]{src_dir}[/green]\n"
                f"Destination: [green]{dest_dir}[/green]",
                title="Starting Processing",
            )
        )

        # Initialize components
        file_system = FileSystem(
            cbm_dir=cbm_dir,
            src_dir=src_dir,
            dest_dir=dest_dir
        )
        openai_client = OpenAI(api_key=config["openai_key"])
        markitdown = MarkItDownWrapper(
            client=openai_client,
            cbm_dir=cbm_dir,
        )

        # Create processor
        processor = MarkdownProcessorV2(
            markitdown=markitdown,
            file_system=file_system,
            src_dir=src_dir,
            dest_dir=dest_dir,
        )

        # Process files and show statistics
        logger.info("Starting markdown processing...")
        stats = processor.process_all()

        # Display summary
        display_summary(stats)

        # Exit with error if any files failed
        if stats["files_errored"] > 0:
            sys.exit(1)

    except Exception as e:
        error_console.print(f"[red]Error: {str(e)}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
