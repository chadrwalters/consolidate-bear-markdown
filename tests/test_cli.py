"""Tests for CLI functionality."""

from pathlib import Path
from typing import Dict, Any
from unittest.mock import patch, Mock
import pytest

def test_load_config(tmp_path: Path) -> None:
    """Test loading configuration from file."""
    # Create test config file
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        'srcDir = "/test/src"\n'
        'destDir = "/test/dest"\n'
        'openai_key = "test-key"\n'
        'logLevel = "INFO"\n'
    )

    # Load config
    from src.cli import load_config
    config = load_config(config_path)

    # Verify config
    assert config["srcDir"] == "/test/src"
    assert config["destDir"] == "/test/dest"
    assert config["openai_key"] == "test-key"
    assert config["logLevel"] == "INFO"


def test_validate_config() -> None:
    """Test configuration validation."""
    # Valid config
    valid_config = {
        "srcDir": "/test/src",
        "destDir": "/test/dest",
        "openai_key": "test-key",
        "logLevel": "INFO"
    }

    # Invalid configs
    missing_src = {k: v for k, v in valid_config.items() if k != "srcDir"}
    missing_dest = {k: v for k, v in valid_config.items() if k != "destDir"}
    missing_key = {k: v for k, v in valid_config.items() if k != "openai_key"}
    invalid_log_level = {**valid_config, "logLevel": "INVALID"}

    # Test validation
    from src.cli import validate_config
    # Valid config should not raise
    validate_config(valid_config)

    # Invalid configs should raise ValueError
    with pytest.raises(ValueError, match="Missing required config field: srcDir"):
        validate_config(missing_src)
    with pytest.raises(ValueError, match="Missing required config field: destDir"):
        validate_config(missing_dest)
    with pytest.raises(ValueError, match="Missing required config field: openai_key"):
        validate_config(missing_key)
    with pytest.raises(ValueError, match="Invalid log level"):
        validate_config(invalid_log_level)


def test_main(tmp_path: Path) -> None:
    """Test main entry point."""
    # Create test config
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        'srcDir = "/test/src"\n'
        'destDir = "/test/dest"\n'
        'openai_key = "test-key"\n'
        'logLevel = "INFO"\n'
    )

    # Mock dependencies
    mock_processor = Mock()
    mock_processor.process_all.return_value = {
        "files": {
            "total": 3,
            "success": 3,
            "error": 0,
        },
        "attachments": {
            "total": 6,
            "success": 6,
            "error": 0,
            "skipped": 0,
        },
        "errors": [],
    }

    with patch("sys.argv", ["prog", "-c", str(config_path)]), \
        patch("src.cli.MarkdownProcessorV2", return_value=mock_processor), \
        patch("src.cli.setup_logging"), \
        patch("src.cli.MarkItDown") as mock_markitdown_cls, \
        patch("src.cli.OpenAI"), \
        patch("src.cli.console.print") as mock_print:

        # Run main
        from src.cli import main
        main()

        # Verify processor was called
        mock_processor.process_all.assert_called_once()
