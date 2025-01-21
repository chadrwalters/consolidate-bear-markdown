"""Tests for the image converter module."""

import os
import shutil
from pathlib import Path
from typing import Generator
from unittest.mock import patch

import pytest
from PIL import Image

from src.image_converter import ImageConverter

@pytest.fixture
def converter(tmp_path: Path) -> ImageConverter:
    """Create an ImageConverter instance for testing."""
    return ImageConverter(cbm_dir=tmp_path / ".cbm")

@pytest.fixture
def converter_with_temp_dir(tmp_path: Path) -> ImageConverter:
    """Create an ImageConverter instance with a temp directory for testing."""
    return ImageConverter(cbm_dir=tmp_path / ".cbm")

def test_init(tmp_path: Path) -> None:
    """Test ImageConverter initialization."""
    cbm_dir = tmp_path / ".cbm"
    converter = ImageConverter(cbm_dir=cbm_dir)

    assert converter.cbm_dir == cbm_dir
    assert converter.temp_dir == cbm_dir / "temp_images"
    assert converter.temp_dir.exists()

def test_convert_if_needed_supported_format(converter: ImageConverter, tmp_path: Path) -> None:
    """Test that supported formats are not converted."""
    # Create a test JPEG
    test_image = tmp_path / "test.jpg"
    Image.new('RGB', (100, 100)).save(test_image)

    result = converter.convert_if_needed(test_image)
    assert result == test_image

def test_convert_if_needed_nonexistent_file(converter: ImageConverter, tmp_path: Path) -> None:
    """Test handling of nonexistent files."""
    with pytest.raises(FileNotFoundError):
        converter.convert_if_needed(tmp_path / "nonexistent.jpg")

def test_convert_with_pillow(converter: ImageConverter, tmp_path: Path) -> None:
    """Test image conversion using Pillow."""
    # Create a test PNG with transparency
    test_image = tmp_path / "test.png"
    img = Image.new('RGBA', (100, 100), (255, 0, 0, 128))
    img.save(test_image)

    result = converter.convert_if_needed(test_image)
    assert result is not None
    assert result.suffix == '.jpg'

    # Verify the converted image
    with Image.open(result) as converted:
        assert converted.mode == 'RGB'
        assert converted.size == (100, 100)

@pytest.mark.skipif(os.uname().sysname != 'Darwin', reason="sips only available on macOS")
def test_convert_heic_with_sips(converter: ImageConverter, tmp_path: Path) -> None:
    """Test HEIC conversion using sips on macOS."""
    test_image = tmp_path / "test.heic"
    test_image.write_bytes(b"fake heic")  # Create a fake HEIC file

    # Mock sips conversion
    with patch('subprocess.run') as mock_run:
        mock_run.return_value.returncode = 0
        result = converter.convert_if_needed(test_image)
        assert result is not None
        assert result.suffix == '.jpg'
        mock_run.assert_called_once_with(
            ['sips', '-s', 'format', 'jpeg', str(test_image), '--out', str(result)],
            capture_output=True,
            text=True
        )

def test_convert_heic_with_pillow_fallback(converter: ImageConverter, tmp_path: Path) -> None:
    """Test HEIC conversion falling back to Pillow."""
    test_image = tmp_path / "test.heic"

    # Create a fake HEIC file
    test_image.write_bytes(b"fake heic data")

    # Mock sips failure and Pillow conversion
    with patch('subprocess.run') as mock_run, \
         patch('PIL.Image.open') as mock_open:
        # Make sips fail
        mock_run.side_effect = Exception("sips failed")

        # Mock Pillow operations
        mock_img = mock_open.return_value.__enter__.return_value
        mock_img.mode = 'RGB'
        mock_img.size = (100, 100)

        result = converter.convert_if_needed(test_image)

        assert mock_run.called  # sips was attempted
        assert mock_open.called  # Pillow was used as fallback
        assert result is not None
        assert result.suffix == '.jpg'

def test_cleanup(converter: ImageConverter, tmp_path: Path) -> None:
    """Test cleanup of temporary files."""
    # Create some test files
    test_file = converter.temp_dir / "test.jpg"
    test_file.write_bytes(b"test data")

    converter.cleanup()

    assert not test_file.exists()
    assert not converter.temp_dir.exists()
