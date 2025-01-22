"""Command line interface for markdown processing."""

import logging
from pathlib import Path
import sys
from typing import Dict

from openai import OpenAI
import tomli

from .converter_factory import ConverterFactory
from .file_system import FileSystem
from .markdown_processor_v2 import MarkdownProcessorV2

logger = logging.getLogger(__name__)


def validate_config(config: Dict) -> None:
    """Validate configuration.

    Args:
        config: Configuration dictionary

    Raises:
        ValueError: If configuration is invalid
    """
    required_fields = {"input_dir", "output_dir", "openai_api_key"}
    missing_fields = required_fields - set(config.keys())
    if missing_fields:
        raise ValueError(f"Missing required config fields: {missing_fields}")

    # Validate log level if present
    if "log_level" in config:
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if config["log_level"].upper() not in valid_levels:
            raise ValueError(
                f"Invalid log level: {config['log_level']}. "
                f"Must be one of: {', '.join(valid_levels)}"
            )


def setup_logging(config: Dict) -> None:
    """Set up logging configuration.

    Args:
        config: Configuration dictionary
    """
    log_level = config.get("log_level", "INFO").upper()
    logging.basicConfig(
        level=log_level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )


def process_files(config: Dict) -> None:
    """Process markdown files according to configuration.

    Args:
        config: Configuration dictionary
    """
    try:
        # Set up paths
        src_dir = Path(config["input_dir"])
        dest_dir = Path(config["output_dir"])
        cbm_dir = Path(config.get("cbm_dir", ".cbm"))

        # Initialize OpenAI client
        client = OpenAI(api_key=config["openai_api_key"])

        # Initialize components
        fs = FileSystem(cbm_dir=cbm_dir, src_dir=src_dir, dest_dir=dest_dir)

        # Create converter factory
        converter_factory = ConverterFactory(cbm_dir=cbm_dir, openai_client=client)

        # Create processor
        processor = MarkdownProcessorV2(
            converter_factory=converter_factory,
            file_system=fs,
            src_dir=src_dir,
            dest_dir=dest_dir,
        )

        # Process all files and print stats
        processor.process_all()
        print(processor.format_stats())

    except Exception as e:
        logger.error(f"Error during processing: {e}")
        raise


def main() -> None:
    """Main entry point."""
    try:
        # Check arguments
        if len(sys.argv) != 3 or sys.argv[1] != "-c":
            print("Usage: python -m src.cli -c config.toml")
            sys.exit(1)

        # Read config file
        config_path = Path(sys.argv[2])
        if not config_path.exists():
            print(f"Config file not found: {config_path}")
            sys.exit(1)

        with open(config_path, "rb") as f:
            config = tomli.load(f)

        # Validate and setup
        validate_config(config)
        setup_logging(config)

        # Process files
        process_files(config)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
