"""Console and logging configuration management."""
import logging
import os
import warnings
from pathlib import Path
from typing import Optional

class ConsoleManager:
    """Manages console output and logging configuration."""

    def __init__(self, cbm_dir: str = ".cbm", log_level: str = "WARNING"):
        """Initialize console manager.

        Args:
            cbm_dir: Directory for logs (default: .cbm)
            log_level: Logging level for console (default: WARNING)
        """
        self.cbm_dir = Path(cbm_dir)
        self.log_level = getattr(logging, log_level.upper())
        self.log_file: Optional[Path] = None

    def setup_logging(self) -> None:
        """Configure logging with console and file handlers."""
        # Create logs directory if it doesn't exist
        log_dir = self.cbm_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        # Setup log file
        self.log_file = log_dir / "debug.log"

        # Configure root logger
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG)  # Capture all logs

        # Remove existing handlers
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)

        # Console handler - WARNING level
        console = logging.StreamHandler()
        console.setLevel(self.log_level)
        console_fmt = logging.Formatter('%(levelname)s: %(message)s')
        console.setFormatter(console_fmt)
        logger.addHandler(console)

        # File handler - DEBUG level
        file_handler = logging.FileHandler(self.log_file)
        file_handler.setLevel(logging.DEBUG)
        file_fmt = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_fmt)
        logger.addHandler(file_handler)

        # Suppress warnings if log level is ERROR
        if self.log_level >= logging.ERROR:
            warnings.filterwarnings('ignore')
            # Specifically handle DeprecationWarning
            warnings.filterwarnings('ignore', category=DeprecationWarning)

        # Log initial setup
        logging.debug(f"Logging initialized. Debug log: {self.log_file}")
        logging.debug(f"Console log level: {logging.getLevelName(self.log_level)}")

    def get_log_file(self) -> Optional[Path]:
        """Get the current log file path.

        Returns:
            Path to log file if logging is setup, None otherwise
        """
        return self.log_file
