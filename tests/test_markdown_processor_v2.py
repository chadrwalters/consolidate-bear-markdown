"""Tests for the simplified markdown processor."""

import pytest
from pathlib import Path
from typing import Dict, Tuple, Any, cast, Optional
from unittest.mock import Mock, MagicMock, create_autospec
from unittest.mock import patch

from src.markdown_processor_v2 import MarkdownProcessorV2
from src.file_system import FileSystem, MarkdownFile
from src.markitdown_wrapper import MarkItDownWrapper
from src.file_manager import FileManager


@pytest.fixture
def mock_markitdown() -> Mock:
    """Create a mock MarkItDown wrapper."""
    mock = Mock(spec=MarkItDownWrapper)
    mock.convert_file.return_value = {
        "success": True,
        "content": "Converted content",
        "error": None
    }
    return mock


@pytest.fixture
def mock_file_system(tmp_path: Path) -> Mock:
    """Create a mock file system."""
    mock = Mock(spec=FileSystem)
    mock.cbm_dir = tmp_path / ".cbm"
    mock.src_dir = tmp_path / "src"
    mock.dest_dir = tmp_path / "dest"
    mock.src_dir.mkdir(parents=True)
    mock.dest_dir.mkdir(parents=True)
    return mock


@pytest.fixture
def mock_file_manager(tmp_path: Path) -> Mock:
    """Create a mock file manager."""
    mock = Mock(spec=FileManager)
    mock.normalize_path.side_effect = lambda p: p
    mock.validate_path.return_value = True
    return mock


@pytest.fixture
def processor(
    tmp_path: Path,
    mock_markitdown: Mock,
    mock_file_system: Mock,
    monkeypatch: pytest.MonkeyPatch
) -> MarkdownProcessorV2:
    """Create a markdown processor with mock dependencies."""
    # Create necessary directories
    src_dir = tmp_path / "src"
    dest_dir = tmp_path / "dest"
    cbm_dir = tmp_path / ".cbm"
    src_dir.mkdir(parents=True, exist_ok=True)
    dest_dir.mkdir(parents=True, exist_ok=True)
    cbm_dir.mkdir(parents=True, exist_ok=True)

    # Update mock file system paths
    mock_file_system.cbm_dir = cbm_dir
    mock_file_system.src_dir = src_dir
    mock_file_system.dest_dir = dest_dir

    processor = MarkdownProcessorV2(
        markitdown=mock_markitdown,
        file_system=mock_file_system,
        src_dir=src_dir,
        dest_dir=dest_dir
    )
    return processor


def test_process_attachment_success(processor: MarkdownProcessorV2, tmp_path: Path) -> None:
    """Test successful attachment processing."""
    # Create test files in src directory
    src_dir = tmp_path / "src"
    attachment_path = src_dir / "test.jpg"
    attachment_path.touch()

    md_file = Mock(spec=MarkdownFile)
    md_file.md_path = src_dir / "test.md"
    md_file.attachment_dir = src_dir

    result = processor.process_attachment(md_file, attachment_path)
    assert result["success"] is True
    assert result["content"] == "Converted content"
    assert result["error"] is None


def test_process_attachment_missing_file(processor: MarkdownProcessorV2, tmp_path: Path) -> None:
    """Test processing a missing attachment."""
    src_dir = tmp_path / "src"
    md_file = Mock(spec=MarkdownFile)
    md_file.md_path = src_dir / "test.md"
    md_file.attachment_dir = src_dir
    attachment_path = src_dir / "nonexistent.jpg"

    result = processor.process_attachment(md_file, attachment_path)
    assert result["success"] is False
    assert "File not found" in result["error"]
    assert result["content"] is None


def test_process_attachment_conversion_error(
    processor: MarkdownProcessorV2,
    mock_markitdown: Mock,
    tmp_path: Path
) -> None:
    """Test handling of conversion errors."""
    # Setup mock to return error
    mock_markitdown.convert_file.return_value = {
        "success": False,
        "error": "Conversion failed",
        "content": None
    }

    # Create test files in src directory
    src_dir = tmp_path / "src"
    attachment_path = src_dir / "test.jpg"
    attachment_path.touch()
    md_file = Mock(spec=MarkdownFile)
    md_file.md_path = src_dir / "test.md"
    md_file.attachment_dir = src_dir

    result = processor.process_attachment(md_file, attachment_path)
    assert result["success"] is False
    assert result["error"] == "Conversion failed"
    assert result["content"] is None


def test_process_markdown_file(processor: MarkdownProcessorV2, tmp_path: Path) -> None:
    """Test processing a markdown file with references."""
    # Create test files in src directory
    src_dir = tmp_path / "src"
    md_path = src_dir / "test.md"
    attachment_dir = src_dir / "test"
    attachment_dir.mkdir(parents=True, exist_ok=True)

    # Create test files
    image_path = attachment_dir / "image.jpg"
    image_path.touch()
    pdf_path = attachment_dir / "doc.pdf"
    pdf_path.touch()

    # Create markdown content with references
    content = """
    # Test Document

    ![Image](image.jpg)<!-- {"embed": true} -->
    [Document](doc.pdf)<!-- {"embed": true} -->
    [Skip this](skip.txt)
    """
    md_path.write_text(content)

    md_file = Mock(spec=MarkdownFile)
    md_file.md_path = md_path
    md_file.attachment_dir = attachment_dir
    def mock_get_attachment(path: str) -> Optional[Path]:
        if path == "image.jpg":
            return image_path
        elif path == "doc.pdf":
            return pdf_path
        return None
    md_file.get_attachment.side_effect = mock_get_attachment

    processed_content, stats = processor.process_markdown_file(md_file)

    # Check statistics
    assert stats["success"] == 2  # Image and embedded document
    assert stats["skipped"] == 1  # Non-embedded link
    assert stats["missing"] == 0
    assert stats["error"] == 0

    # Check content modifications
    assert "<details>" in processed_content
    assert "Converted content" in processed_content
    assert "![Image](image.jpg)" in processed_content
    assert "[Document](doc.pdf)" in processed_content
    assert "[Skip this](skip.txt)" in processed_content


def test_process_markdown_file_invalid_path(
    processor: MarkdownProcessorV2,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test processing a markdown file with an invalid path."""
    # Create test files
    md_path = tmp_path / "test.md"
    attachment_dir = tmp_path / "test"
    attachment_dir.mkdir()

    # Create markdown content with references
    content = """
    # Test Document

    ![Image](invalid.jpg)
    """
    md_path.write_text(content)

    md_file = Mock(spec=MarkdownFile)
    md_file.md_path = md_path
    md_file.attachment_dir = attachment_dir
    md_file.get_attachment.return_value = attachment_dir / "invalid.jpg"

    # Make path validation fail
    monkeypatch.setattr(processor.file_manager, "validate_path", lambda p: False)

    processed_content, stats = processor.process_markdown_file(md_file)

    # Check statistics
    assert stats["error"] == 1
    assert stats["success"] == 0

    # Check error message
    assert "Invalid or inaccessible path" in processed_content


def test_process_all(processor: MarkdownProcessorV2, mock_file_system: Mock, tmp_path: Path) -> None:
    """Test processing all markdown files."""
    # Setup mock file system to return test files
    src_dir = tmp_path / "src"
    md_path = src_dir / "test.md"
    attachment_dir = src_dir / "test"
    attachment_dir.mkdir(parents=True, exist_ok=True)
    md_path.touch()

    md_file = Mock(spec=MarkdownFile)
    md_file.md_path = md_path
    md_file.attachment_dir = attachment_dir
    mock_file_system.discover_markdown_files.return_value = [md_file]

    # Mock process_markdown_file
    mock_result = ("Processed content", {
        "success": 1,
        "error": 0,
        "missing": 0,
        "skipped": 1
    })

    with patch.object(processor, 'process_markdown_file', return_value=mock_result):
        stats = processor.process_all()

        assert stats["files_processed"] == 1
        assert stats["files_errored"] == 0
        assert stats["success"] == 1
        assert stats["skipped"] == 1
        assert stats["missing"] == 0
        assert stats["error"] == 0

        # Verify the output file was created
        output_path = tmp_path / "dest" / "test.md"
        assert output_path.parent.exists()


def test_process_all_with_errors(
    processor: MarkdownProcessorV2,
    mock_file_system: Mock,
    tmp_path: Path
) -> None:
    """Test handling of errors during batch processing."""
    # Setup mock to return multiple files
    src_dir = tmp_path / "src"
    md_files = [
        Mock(spec=MarkdownFile, md_path=src_dir / "success.md"),
        Mock(spec=MarkdownFile, md_path=src_dir / "error.md")
    ]
    mock_file_system.discover_markdown_files.return_value = md_files

    # Mock process_markdown_file with different behaviors
    def mock_process(md_file: MarkdownFile) -> Tuple[str, Dict[str, int]]:
        if md_file.md_path.name == "error.md":
            raise Exception("Processing failed")
        return "content", {"success": 1, "error": 0, "missing": 0, "skipped": 0}

    with patch.object(processor, 'process_markdown_file', side_effect=mock_process):
        stats = processor.process_all()

        assert stats["files_processed"] == 1
        assert stats["files_errored"] == 1
        assert stats["success"] == 1
        assert stats["error"] == 0


def test_cleanup_on_deletion(processor: MarkdownProcessorV2) -> None:
    """Test cleanup is called when processor is deleted."""
    # Create a spy on the file manager's cleanup method
    with patch.object(processor.file_manager, 'cleanup') as cleanup_spy:
        # Trigger deletion
        processor.__del__()

        # Verify cleanup was called
        cleanup_spy.assert_called_once()


def test_process_markdown_file_non_embedded_attachments(processor: MarkdownProcessorV2, tmp_path: Path) -> None:
    """Test processing a markdown file with non-embedded attachments."""
    # Create test files in src directory
    src_dir = tmp_path / "src"
    md_path = src_dir / "test.md"
    attachment_dir = src_dir / "test"
    attachment_dir.mkdir(parents=True, exist_ok=True)

    # Create test attachments
    image_path = attachment_dir / "image.jpg"
    image_path.touch()
    pdf_path = attachment_dir / "doc.pdf"
    pdf_path.touch()

    # Create markdown content with references - explicitly set embed=false
    content = """
    # Test Document

    ![Image](image.jpg)<!--{"embed": false}-->
    [Document](doc.pdf)<!--{"embed": false}-->
    """
    md_path.write_text(content)

    # Set up mock markdown file
    md_file = Mock(spec=MarkdownFile)
    md_file.md_path = md_path
    md_file.attachment_dir = attachment_dir
    md_file.get_attachment.side_effect = lambda p: attachment_dir / p

    processed_content, stats = processor.process_markdown_file(md_file)

    # Check statistics - both attachments should be skipped since they have embed=false
    assert stats["success"] == 0
    assert stats["error"] == 0
    assert stats["missing"] == 0
    assert stats["skipped"] == 2  # Both attachments should be skipped
