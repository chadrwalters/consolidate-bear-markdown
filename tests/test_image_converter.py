"""Tests for image conversion functionality."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.converters.image_converter import ImageConverter


@pytest.fixture
def clean_tmp_path(tmp_path: Path) -> Path:
    """Create a clean temporary directory."""
    test_dir = tmp_path / "test"
    test_dir.mkdir()
    return test_dir


def test_svg_conversion(clean_tmp_path: Path) -> None:
    """Test SVG to PNG conversion."""
    # Create test SVG file
    svg_content = """<?xml version="1.0" encoding="UTF-8"?>
    <svg width="100" height="100" xmlns="http://www.w3.org/2000/svg">
        <rect width="100" height="100" fill="blue"/>
    </svg>"""
    svg_file = clean_tmp_path / "test.svg"
    svg_file.write_text(svg_content)

    # Convert SVG
    converter = ImageConverter(openai_client=Mock(), cbm_dir=clean_tmp_path)
    output_path = clean_tmp_path / "test.png"

    # Mock both cairosvg and subprocess.run
    with (
        patch.dict("sys.modules", {"cairosvg": None}),
        patch("subprocess.run") as mock_run,
    ):
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = b""
        mock_result.stderr = b""
        mock_run.return_value = mock_result

        # Test conversion
        result = converter._convert_to_png(svg_file, output_path)
        assert result is True

        # Verify inkscape was called correctly
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "inkscape" in args[0]
        assert str(svg_file) in args
        assert str(output_path) in args


def test_heic_conversion(clean_tmp_path: Path) -> None:
    """Test HEIC conversion."""
    with patch("src.converters.image_converter.HEIF_SUPPORT", True):
        converter = ImageConverter(openai_client=Mock(), cbm_dir=clean_tmp_path)
        assert converter.SUPPORTED_EXTENSIONS == {
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".webp",
            ".heic",
            ".heif",
            ".svg",
        }


def test_cleanup(clean_tmp_path: Path) -> None:
    """Test cleanup functionality."""
    converter = ImageConverter(openai_client=Mock(), cbm_dir=clean_tmp_path)

    # Create some test files
    test_file = converter.temp_dir / "test.png"
    test_file.touch()

    # Cleanup
    converter.cleanup()
    assert not test_file.exists()
    assert not converter.temp_dir.exists()
