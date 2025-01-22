"""Tests for CLI functionality."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest


def test_validate_config() -> None:
    """Test configuration validation."""
    # Valid config
    valid_config = {
        "input_dir": "/tmp/test/src",
        "output_dir": "/tmp/test/dest",
        "openai_api_key": "test-key",
        "log_level": "INFO",
    }

    # Invalid configs
    missing_src = {k: v for k, v in valid_config.items() if k != "input_dir"}
    missing_dest = {k: v for k, v in valid_config.items() if k != "output_dir"}
    missing_key = {k: v for k, v in valid_config.items() if k != "openai_api_key"}
    invalid_log_level = {**valid_config, "log_level": "INVALID"}

    # Test validation
    from src.cli import validate_config

    # Valid config should not raise
    validate_config(valid_config)

    # Invalid configs should raise ValueError
    with pytest.raises(ValueError):
        validate_config(missing_src)
    with pytest.raises(ValueError):
        validate_config(missing_dest)
    with pytest.raises(ValueError):
        validate_config(missing_key)
    with pytest.raises(ValueError, match="Invalid log level"):
        validate_config(invalid_log_level)


def test_main(tmp_path: Path) -> None:
    """Test main entry point."""
    # Create test directories
    src_dir = tmp_path / "src"
    dest_dir = tmp_path / "dest"
    src_dir.mkdir(parents=True)
    dest_dir.mkdir(parents=True)

    # Create test config
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        f'input_dir = "{src_dir}"\n'
        f'output_dir = "{dest_dir}"\n'
        'openai_api_key = "test-key"\n'
        'log_level = "INFO"\n'
    )

    # Mock dependencies
    mock_processor = Mock()
    mock_processor.process_all.return_value = {
        "files_processed": 3,
        "files_errored": 0,
        "success": 6,
        "error": 0,
        "missing": 0,
        "skipped": 0,
        "errors": [],
    }
    mock_processor.format_stats.return_value = "Stats summary"

    with (
        patch("sys.argv", ["prog", "-c", str(config_path)]),
        patch("src.cli.MarkdownProcessorV2", return_value=mock_processor),
        patch("src.cli.setup_logging"),
        patch("src.cli.OpenAI"),
    ):
        # Run main
        from src.cli import main

        main()

        # Verify processor was called
        mock_processor.process_all.assert_called_once()
        mock_processor.format_stats.assert_called_once()
