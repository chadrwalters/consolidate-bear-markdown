"""Tests for MarkItDown wrapper."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import Generator

from src.markitdown_wrapper import MarkItDownWrapper


@pytest.fixture
def mock_markitdown() -> Generator[MagicMock, None, None]:
    """Mock MarkItDown."""
    with patch("src.markitdown_wrapper.MarkItDownWrapper") as mock:
        yield mock


@pytest.fixture
def wrapper(tmp_path: Path, mock_openai: MagicMock) -> MarkItDownWrapper:
    """Create MarkItDownWrapper instance."""
    return MarkItDownWrapper(
        client=mock_openai,
        cbm_dir=str(tmp_path / ".cbm"),
    )


@pytest.fixture
def mock_openai() -> Generator[MagicMock, None, None]:
    """Mock OpenAI client."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content="Test description"))]
    mock_client.chat.completions.create.return_value = mock_response
    return mock_client


def test_init(mock_openai: MagicMock) -> None:
    """Test initialization."""
    wrapper = MarkItDownWrapper(client=mock_openai, cbm_dir=".cbm")
    assert wrapper.client == mock_openai
    assert wrapper.max_retries == 3
    assert wrapper.retry_delay == 1


def test_convert_file(mock_openai: MagicMock, tmp_path: Path) -> None:
    """Test file conversion."""
    wrapper = MarkItDownWrapper(client=mock_openai, cbm_dir=".cbm")

    # Create a test file
    test_file = tmp_path / "test.txt"
    test_file.write_text("Test content")

    result = wrapper.convert_file(test_file)
    assert result["success"] is True
    assert "content" in result
    assert result["type"] == "file"


def test_process_image(mock_openai: MagicMock, tmp_path: Path) -> None:
    """Test image processing."""
    wrapper = MarkItDownWrapper(client=mock_openai, cbm_dir=".cbm")

    # Create a test image
    test_image = tmp_path / "test.jpg"
    test_image.touch()

    result = wrapper.process_image(test_image)
    assert result["success"] is True
    assert "text" in result
