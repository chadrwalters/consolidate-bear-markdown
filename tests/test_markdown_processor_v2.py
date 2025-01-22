"""Tests for the simplified markdown processor."""

from pathlib import Path
from typing import Optional
from unittest.mock import Mock, patch

import pytest
import os
import time
from openai import OpenAI

from src.converter_factory import ConverterFactory
from src.file_manager import FileManager
from src.file_system import FileSystem, MarkdownFile
from src.markdown_processor_v2 import MarkdownProcessorV2


@pytest.fixture
def mock_converter_factory() -> Mock:
    """Create a mock ConverterFactory."""
    mock = Mock(spec=ConverterFactory)
    mock.convert_file.return_value = {
        "success": True,
        "content": "Converted content",
        "error": None,
        "text_content": "Text content",
        "text": "Text",
        "type": "document",
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
def processor(tmp_path: Path) -> MarkdownProcessorV2:
    """Create a processor instance for testing."""
    src_dir = tmp_path / "src"
    src_dir.mkdir(exist_ok=True)
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir(exist_ok=True)
    cbm_dir = tmp_path / ".cbm"
    cbm_dir.mkdir(exist_ok=True)

    # Create mock components
    fs = Mock(spec=FileSystem)
    fs.cbm_dir = cbm_dir
    fs.src_dir = src_dir
    fs.dest_dir = dest_dir
    fs.discover_markdown_files = Mock(return_value=[])  # Default to empty list

    # Set up converter factory with default success response
    converter_factory = Mock(spec=ConverterFactory)
    converter_factory.converters = {}  # Add this to prevent cleanup errors
    converter_factory.convert_file = Mock(return_value={
        "success": True,
        "content": "Converted content",
        "error": None,
        "text_content": "Text content",
        "text": "Text",
        "type": "text",
    })

    processor = MarkdownProcessorV2(
        converter_factory=converter_factory,
        file_system=fs,
        src_dir=src_dir,
        dest_dir=dest_dir,
    )
    return processor


def test_process_attachment_success(processor: MarkdownProcessorV2) -> None:
    """Test successful attachment processing."""
    # Create test files in src directory
    src_file = processor.src_dir / "test.md"
    src_file.parent.mkdir(parents=True, exist_ok=True)
    src_file.write_text("test")

    attachment_path = processor.src_dir / "test.jpg"
    attachment_path.write_text("fake image")

    result = processor.process_attachment(src_file, attachment_path)
    assert result["success"] is True
    assert result["content"] == "Converted content"
    assert result["error"] is None


def test_process_attachment_missing_file(processor: MarkdownProcessorV2) -> None:
    """Test handling of missing attachment files."""
    # Create test files in src directory
    src_file = processor.src_dir / "test.md"
    src_file.parent.mkdir(parents=True, exist_ok=True)
    src_file.write_text("test")

    attachment_path = processor.src_dir / "missing.jpg"

    result = processor.process_attachment(src_file, attachment_path)
    assert result["success"] is False
    assert "not found" in result["error"]


def test_process_attachment_conversion_error(processor: MarkdownProcessorV2) -> None:
    """Test handling of conversion errors."""
    # Create test files in src directory
    src_file = processor.src_dir / "test.md"
    src_file.parent.mkdir(parents=True, exist_ok=True)
    src_file.write_text("test")

    attachment_path = processor.src_dir / "test.jpg"
    attachment_path.write_text("fake image")

    # Set up mock to return error
    processor.converter_factory.convert_file.return_value = {
        "success": False,
        "error": "Conversion failed",
        "content": None,
        "text_content": None,
        "text": None,
        "type": "unknown",
        "error_type": "conversion_error",
    }

    result = processor.process_attachment(src_file, attachment_path)
    assert result["success"] is False
    assert result["error"] == "Conversion failed"


def test_process_markdown_file(processor: MarkdownProcessorV2) -> None:
    """Test processing a markdown file with references."""
    # Create test files in src directory
    src_file = processor.src_dir / "test.md"
    src_file.parent.mkdir(parents=True, exist_ok=True)

    attach_dir = processor.src_dir / "test"
    attach_dir.mkdir()

    # Create test files
    image_path = attach_dir / "image.jpg"
    image_path.write_text("fake image")
    pdf_path = attach_dir / "doc.pdf"
    pdf_path.write_text("fake pdf")

    # Create markdown content with references
    content = """
    # Test Document

    ![Image](image.jpg)<!-- {"embed": true} -->
    [Document](doc.pdf)<!-- {"embed": true} -->
    [Skip this](skip.txt)
    """
    src_file.write_text(content)

    md_file = MarkdownFile(
        md_path=src_file,
        attachment_dir=attach_dir
    )

    processed_content, stats = processor.process_markdown_file(md_file)

    # Check statistics
    assert stats["success"] == 2  # Image and embedded document
    assert stats["error"] == 0
    assert stats["skipped"] == 1  # Skip this reference

    # Check content
    assert "Converted content" in processed_content
    assert "Skip this" in processed_content


def test_process_markdown_file_invalid_path(processor: MarkdownProcessorV2) -> None:
    """Test handling of invalid paths in markdown files."""
    # Create test files in src directory
    src_file = processor.src_dir / "test.md"
    src_file.parent.mkdir(parents=True, exist_ok=True)

    # Create markdown content with invalid reference
    content = """
    # Test Document

    ![Invalid](../outside.jpg)<!-- {"embed": true} -->
    """
    src_file.write_text(content)

    md_file = MarkdownFile(
        md_path=src_file,
        attachment_dir=None
    )

    processed_content, stats = processor.process_markdown_file(md_file)

    # Check statistics
    assert stats["error"] == 1
    assert stats["success"] == 0

    # Check content includes error message
    assert "Invalid or inaccessible path" in processed_content


def test_process_all(processor: MarkdownProcessorV2) -> None:
    """Test processing all files."""
    # Create test files in src directory
    src_file = processor.src_dir / "test.md"
    src_file.parent.mkdir(parents=True, exist_ok=True)
    src_file.write_text("test")

    # Set up mock to return our test file
    md_file = MarkdownFile(md_path=src_file, attachment_dir=None)
    processor.fs.discover_markdown_files.return_value = [md_file]

    # Set up mock for successful processing
    processor.process_markdown_file = Mock(return_value=("processed", {
        "success": 1,
        "error": 0,
        "missing": 0,
        "skipped": 0,
        "total": 1
    }))

    # Process files
    stats = processor.process_all()

    # Check statistics
    assert stats["files_processed"] == 1
    assert stats["files_errored"] == 0
    assert stats["files_skipped"] == 0
    assert stats["files_unchanged"] == 0
    assert stats["success"] == 1
    assert stats["error"] == 0
    assert stats["skipped"] == 0
    assert stats["total"] == 1


def test_should_process_force_generation(processor: MarkdownProcessorV2):
    """Test that force_generation=True always returns True."""
    # Create a test file in src_dir
    src_file = processor.src_dir / "test.md"
    src_file.parent.mkdir(parents=True, exist_ok=True)
    src_file.write_text("test")

    md_file = MarkdownFile(
        md_path=src_file,
        attachment_dir=None
    )

    # Create processor with force_generation=True
    processor.force_generation = True

    # Should always return True with force_generation
    assert processor.should_process(md_file) is True


def test_should_process_new_file(processor: MarkdownProcessorV2):
    """Test that new files are always processed."""
    # Create a test file in src_dir
    src_file = processor.src_dir / "test.md"
    src_file.parent.mkdir(parents=True, exist_ok=True)
    src_file.write_text("test")

    md_file = MarkdownFile(
        md_path=src_file,
        attachment_dir=None
    )

    # Should return True for new files
    assert processor.should_process(md_file) is True


def test_should_process_modified_markdown(processor: MarkdownProcessorV2):
    """Test that modified markdown files are processed."""
    # Create source file in src_dir
    src_file = processor.src_dir / "test.md"
    src_file.parent.mkdir(parents=True, exist_ok=True)
    src_file.write_text("test")

    md_file = MarkdownFile(
        md_path=src_file,
        attachment_dir=None
    )

    # Create older output file
    out_file = processor.dest_dir / "test.md"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text("old")

    # Ensure source is newer than output
    os.utime(out_file, (time.time() - 100, time.time() - 100))
    os.utime(src_file, (time.time(), time.time()))

    # Should return True for modified files
    assert processor.should_process(md_file) is True


def test_should_process_modified_attachment(processor: MarkdownProcessorV2):
    """Test that files with modified attachments are processed."""
    # Create source files in src_dir
    src_file = processor.src_dir / "test.md"
    src_file.parent.mkdir(parents=True, exist_ok=True)
    src_file.write_text("test")

    attach_dir = processor.src_dir / "test"
    attach_dir.mkdir()
    attach_file = attach_dir / "image.png"
    attach_file.write_text("fake image")

    md_file = MarkdownFile(
        md_path=src_file,
        attachment_dir=attach_dir
    )

    # Create older output file
    out_file = processor.dest_dir / "test.md"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text("old")

    # Make output older than source
    os.utime(out_file, (time.time() - 100, time.time() - 100))
    os.utime(src_file, (time.time() - 50, time.time() - 50))

    # Make attachment newer than output
    os.utime(attach_file, (time.time(), time.time()))

    # Should return True when attachment is modified
    assert processor.should_process(md_file) is True


def test_should_process_unmodified(processor: MarkdownProcessorV2):
    """Test that unmodified files are not processed."""
    # Create source files in src_dir
    src_file = processor.src_dir / "test.md"
    src_file.parent.mkdir(parents=True, exist_ok=True)
    src_file.write_text("test")

    attach_dir = processor.src_dir / "test"
    attach_dir.mkdir()
    attach_file = attach_dir / "image.png"
    attach_file.write_text("fake image")

    md_file = MarkdownFile(
        md_path=src_file,
        attachment_dir=attach_dir
    )

    # Create newer output file
    out_file = processor.dest_dir / "test.md"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text("new")

    # Make everything older than output
    os.utime(src_file, (time.time() - 100, time.time() - 100))
    os.utime(attach_file, (time.time() - 100, time.time() - 100))
    os.utime(out_file, (time.time(), time.time()))

    # Should return False when nothing is modified
    assert processor.should_process(md_file) is False


def test_process_all_skips_unmodified(processor: MarkdownProcessorV2):
    """Test that process_all skips unmodified files."""
    # Create source file in src_dir
    src_file = processor.src_dir / "test.md"
    src_file.parent.mkdir(parents=True, exist_ok=True)
    src_file.write_text("test")

    # Create newer output file
    out_file = processor.dest_dir / "test.md"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text("new")

    # Make source older than output
    os.utime(src_file, (time.time() - 100, time.time() - 100))
    os.utime(out_file, (time.time(), time.time()))

    # Set up mock to return our test file
    md_file = MarkdownFile(md_path=src_file, attachment_dir=None)
    processor.fs.discover_markdown_files.return_value = [md_file]

    # Process files
    stats = processor.process_all()

    # Should have skipped the file
    assert stats["files_unchanged"] == 1
    assert stats["files_processed"] == 0
    assert stats["files_errored"] == 0
    assert stats["files_skipped"] == 0


def test_process_all_processes_modified(processor: MarkdownProcessorV2):
    """Test that process_all processes modified files."""
    # Create source file in src_dir
    src_file = processor.src_dir / "test.md"
    src_file.parent.mkdir(parents=True, exist_ok=True)
    src_file.write_text("test")

    # Create older output file
    out_file = processor.dest_dir / "test.md"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text("old")

    # Make source newer than output
    os.utime(out_file, (time.time() - 100, time.time() - 100))
    os.utime(src_file, (time.time(), time.time()))

    # Set up mock to return our test file
    md_file = MarkdownFile(md_path=src_file, attachment_dir=None)
    processor.fs.discover_markdown_files.return_value = [md_file]

    # Set up mock for successful processing
    processor.process_markdown_file = Mock(return_value=("processed", {"success": 1, "error": 0, "missing": 0, "skipped": 0}))

    # Process files
    stats = processor.process_all()

    # Should have processed the file
    assert stats["files_skipped"] == 0
    assert stats["files_processed"] == 1


def test_process_all_force_generation(processor: MarkdownProcessorV2):
    """Test that process_all processes all files with force_generation."""
    # Create source file in src_dir
    src_file = processor.src_dir / "test.md"
    src_file.parent.mkdir(parents=True, exist_ok=True)
    src_file.write_text("test")

    # Create newer output file
    out_file = processor.dest_dir / "test.md"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text("new")

    # Make source older than output
    os.utime(src_file, (time.time() - 100, time.time() - 100))
    os.utime(out_file, (time.time(), time.time()))

    # Set up mock to return our test file
    md_file = MarkdownFile(md_path=src_file, attachment_dir=None)
    processor.fs.discover_markdown_files.return_value = [md_file]

    # Set up mock for successful processing
    processor.process_markdown_file = Mock(return_value=("processed", {"success": 1, "error": 0, "missing": 0, "skipped": 0}))

    # Enable force generation
    processor.force_generation = True

    # Process files
    stats = processor.process_all()

    # Should have processed all files
    assert stats["files_skipped"] == 0
    assert stats["files_processed"] == 1
