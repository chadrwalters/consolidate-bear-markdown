"""Logging configuration for the consolidate-bear-markdown tool."""

import logging
import os
import atexit
from pathlib import Path
from typing import Optional, List, Dict
from logging import Handler


def _cleanup_logging() -> None:
    """Clean up logging handlers."""
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        try:
            handler.close()
        except Exception:
            pass
        root_logger.removeHandler(handler)


def setup_logging(
    log_level: str = "INFO",
    cbm_dir: str = ".cbm",
    log_file: Optional[str] = "consolidate.log",
) -> None:
    """Set up logging configuration.

    Args:
        log_level: The logging level (DEBUG, INFO, WARNING, ERROR)
        cbm_dir: Directory for system files and logs
        log_file: Optional log file name. If None, logs only to console
    """
    # Register cleanup function
    atexit.register(_cleanup_logging)

    # Create .cbm directory if it doesn't exist
    cbm_path = Path(cbm_dir)
    cbm_path.mkdir(exist_ok=True)

    # Close and remove any existing handlers
    _cleanup_logging()

    # Configure logging format
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    handlers: List[Handler] = []

    # Always add console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(log_format))
    handlers.append(console_handler)

    # Add file handler if log_file specified
    if log_file:
        file_handler = logging.FileHandler(
            os.path.join(cbm_dir, log_file), encoding="utf-8"
        )
        file_handler.setFormatter(logging.Formatter(log_format))
        handlers.append(file_handler)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    for handler in handlers:
        root_logger.addHandler(handler)

    # Suppress pdfminer debug logs
    for logger_name in ['pdfminer.psparser', 'pdfminer.pdfinterp']:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.WARNING)
