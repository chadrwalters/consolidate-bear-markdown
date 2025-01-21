"""Tests for logging configuration."""

import logging
import os
from pathlib import Path

from src.logging_config import setup_logging


def test_setup_logging(tmp_path: Path) -> None:
    """Test logging setup with temporary directory."""
    # Use temporary directory for testing
    cbm_dir = str(tmp_path / ".cbm")
    log_file = "test.log"

    # Setup logging
    setup_logging(log_level="DEBUG", cbm_dir=cbm_dir, log_file=log_file)

    # Verify .cbm directory was created
    assert os.path.exists(cbm_dir)

    # Test logging
    test_message = "Test log message"
    logging.info(test_message)

    # Verify log file was created and contains message
    log_path = os.path.join(cbm_dir, log_file)
    assert os.path.exists(log_path)
    with open(log_path, "r", encoding="utf-8") as f:
        log_content = f.read()
        assert test_message in log_content
