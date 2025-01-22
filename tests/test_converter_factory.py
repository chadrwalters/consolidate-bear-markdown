"""Tests for converter factory functionality."""

from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest

from src.converter_factory import ConverterFactory
from src.converters.binary_converter import BinaryConverter
from src.converters.document_converter import DocumentConverter
from src.converters.image_converter import ImageConverter
from src.converters.spreadsheet_converter import SpreadsheetConverter
from src.converters.text_converter import TextConverter
from src.file_converter import ConversionResult


@pytest.fixture
def mock_openai() -> Generator[MagicMock, None, None]:
    """Mock OpenAI client."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content="Test description"))]
    mock_client.chat.completions.create.return_value = mock_response
    return mock_client


@pytest.fixture
def factory(mock_openai: MagicMock, tmp_path: Path) -> ConverterFactory:
    """Create ConverterFactory instance."""
    return ConverterFactory(
        openai_client=mock_openai,
        cbm_dir=tmp_path / ".cbm",
    )


def test_init(mock_openai: MagicMock, tmp_path: Path) -> None:
    """Test initialization."""
    factory = ConverterFactory(openai_client=mock_openai, cbm_dir=tmp_path / ".cbm")
    assert len(factory.converters) > 0
    assert any(isinstance(c, DocumentConverter) for c in factory.converters)
    assert any(isinstance(c, ImageConverter) for c in factory.converters)
    assert any(isinstance(c, SpreadsheetConverter) for c in factory.converters)
    assert any(isinstance(c, TextConverter) for c in factory.converters)
    assert any(isinstance(c, BinaryConverter) for c in factory.converters)


def test_convert_document(factory: ConverterFactory, tmp_path: Path) -> None:
    """Test document conversion."""
    # Create a test document with content
    test_file = tmp_path / "test.docx"
    test_file.touch()

    mock_result = MagicMock()
    mock_result.stdout = "Converted content"
    mock_result.stderr = ""

    with patch("subprocess.run", return_value=mock_result) as mock_run:
        result: ConversionResult = factory.convert_file(test_file)
        assert result.get("success", False) is True
        assert result.get("type") == "document"
        assert result.get("content") == "Converted content"

        # Verify pandoc was called correctly
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "pandoc" in args
        assert "-f" in args
        assert "docx" in args


def test_convert_image(tmp_path: Path) -> None:
    """Test image conversion."""
    # Create a test image
    test_file = tmp_path / "test.jpg"
    test_file.touch()

    # Create factory without OpenAI client
    factory = ConverterFactory(cbm_dir=tmp_path / ".cbm")

    # Without OpenAI client, should not handle images
    result: ConversionResult = factory.convert_file(test_file)
    assert result.get("success", False) is True
    assert result.get("type") == "binary"  # Falls back to binary converter


def test_convert_spreadsheet(factory: ConverterFactory, tmp_path: Path) -> None:
    """Test spreadsheet conversion."""
    # Create a test spreadsheet with content
    test_file = tmp_path / "test.csv"
    test_file.write_text("col1,col2\nval1,val2")

    result: ConversionResult = factory.convert_file(test_file)
    assert result.get("success", False) is True
    assert result.get("type") == "spreadsheet"
    content = result.get("content")
    assert content is not None
    # Check for table elements without being strict about whitespace
    assert "col1" in content and "col2" in content
    assert "val1" in content and "val2" in content
    assert "|" in content  # Should be a markdown table


def test_convert_text(factory: ConverterFactory, tmp_path: Path) -> None:
    """Test text file conversion."""
    # Create a test text file
    test_file = tmp_path / "test.txt"
    test_file.write_text("Test content")

    result: ConversionResult = factory.convert_file(test_file)
    assert result.get("success", False) is True
    assert result.get("type") == "txt"  # Type is the file extension
    content = result.get("content")
    assert content is not None and "Test content" in content


def test_convert_binary(factory: ConverterFactory, tmp_path: Path) -> None:
    """Test binary file conversion."""
    # Create a test binary file
    test_file = tmp_path / "test.bin"
    test_file.write_bytes(b"binary content")

    result: ConversionResult = factory.convert_file(test_file)
    assert result.get("success", False) is True
    assert result.get("type") == "binary"
    content = result.get("content")
    assert content is not None and "Binary File:" in content


def test_convert_unsupported(factory: ConverterFactory, tmp_path: Path) -> None:
    """Test handling of unsupported file types."""
    # Create a test file with unsupported extension
    test_file = tmp_path / "test.xyz"
    test_file.touch()

    # Should be handled by binary converter
    result: ConversionResult = factory.convert_file(test_file)
    assert result.get("success", False) is True  # Binary converter handles all files
    assert result.get("type") == "binary"
    content = result.get("content")
    assert content is not None and "Binary File:" in content
