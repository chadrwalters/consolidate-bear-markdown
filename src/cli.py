"""Command line interface for the Bear Markdown consolidation tool."""

import argparse
import logging
import sys
from pathlib import Path
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

    # Validate force_generation if present
    if "force_generation" in config and not isinstance(config["force_generation"], bool):
        raise ValueError("force_generation must be a boolean value")


def setup_logging(config: Dict) -> None:
    """Set up logging configuration.

    Args:
        config: Configuration dictionary
    """
    log_level = config.get("log_level", "INFO").upper()

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Configure console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)

    # Remove any existing handlers and add our new one
    root_logger.handlers = []
    root_logger.addHandler(console_handler)

    # Set package loggers to the same level
    logging.getLogger('src').setLevel(log_level)


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
        converter_factory = ConverterFactory(
            cbm_dir=cbm_dir,
            openai_client=client,
            no_image=config.get("no_image", False)
        )

        # Create processor with force_generation setting
        processor = MarkdownProcessorV2(
            converter_factory=converter_factory,
            file_system=fs,
            src_dir=src_dir,
            dest_dir=dest_dir,
            force_generation=config.get("force_generation", False),
            config=config,
        )

        # Process all files and print stats
        processor.process_all()
        print(processor.format_stats())

    except Exception as e:
        logger.error(f"Error during processing: {e}")
        raise


def parse_args() -> argparse.Namespace:
    """Parse command line arguments.

    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(description="Process Bear.app markdown files.")
    parser.add_argument("-c", "--config", required=True, help="Path to config file")
    parser.add_argument(
        "-f", "--force",
        action="store_true",
        help="Force regeneration of all files regardless of modification time",
    )
    parser.add_argument(
        "--no_image",
        action="store_true",
        help="Skip GPT-4o vision analysis for images; insert placeholder instead",
    )
    return parser.parse_args()


def main() -> None:
    """Main entry point."""
    try:
        # Parse arguments
        args = parse_args()

        # Read config file
        config_path = Path(args.config)
        if not config_path.exists():
            print(f"Config file not found: {config_path}")
            sys.exit(1)

        with open(config_path, "rb") as f:
            config = tomli.load(f)

        # Override force_generation from command line if specified
        if args.force:
            config["force_generation"] = True

        # Set no_image from CLI
        config["no_image"] = args.no_image

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
