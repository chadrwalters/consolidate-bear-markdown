"""Core functionality tests for the markdown processing system."""

import pytest
from pathlib import Path
import tempfile
import shutil
import os

from src.markdown_processor_v2 import MarkdownProcessorV2
from src.converter_factory import ConverterFactory
from src.file_system import FileSystem
from src.file_manager import FileManager

@pytest.fixture
def temp_workspace():
    """Create a temporary workspace for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        # Create necessary subdirectories
        (temp_path / ".cbm").mkdir()
        (temp_path / "input").mkdir()
        (temp_path / "output").mkdir()
        yield temp_path

@pytest.fixture
def processor(temp_workspace):
    """Create a MarkdownProcessorV2 instance for testing."""
    cbm_dir = temp_workspace / ".cbm"
    src_dir = temp_workspace / "input"
    dest_dir = temp_workspace / "output"

    converter_factory = ConverterFactory(cbm_dir=cbm_dir)
    file_system = FileSystem(
        cbm_dir=cbm_dir,
        src_dir=src_dir,
        dest_dir=dest_dir
    )

    return MarkdownProcessorV2(
        converter_factory=converter_factory,
        file_system=file_system,
        src_dir=src_dir,
        dest_dir=dest_dir
    )

def test_basic_markdown_processing(temp_workspace, processor):
    """Test basic markdown file processing without attachments."""
    # Create a test markdown file
    input_file = temp_workspace / "input" / "test.md"
    input_file.write_text("# Test Document\nThis is a test.")

    # Process all files
    stats = processor.process_all()

    # Verify output
    output_file = temp_workspace / "output" / "test.md"
    assert output_file.exists()
    assert output_file.read_text() == "# Test Document\nThis is a test."
    assert stats["files_processed"] == 1
    assert stats["error_attachments"] == 0

def test_markdown_with_image_reference(temp_workspace, processor):
    """Test markdown processing with an image reference."""
    # Create test files
    input_dir = temp_workspace / "input"
    (input_dir / "attachments").mkdir()

    # Create a test image
    image_path = input_dir / "attachments" / "test.png"
    with open(image_path, "wb") as f:
        f.write(b"fake png data")  # Minimal fake image data

    # Create markdown with image reference
    md_content = "# Test\n![Test Image](attachments/test.png)"
    (input_dir / "test.md").write_text(md_content)

    # Process files
    stats = processor.process_all()

    # Verify processing occurred
    assert stats["files_processed"] == 1
    assert stats["total_attachments"] >= 1

def test_multiple_markdown_files(temp_workspace, processor):
    """Test processing multiple markdown files simultaneously."""
    input_dir = temp_workspace / "input"

    # Create multiple test files
    files = {
        "doc1.md": "# Document 1\nContent 1",
        "doc2.md": "# Document 2\nContent 2",
        "doc3.md": "# Document 3\nContent 3"
    }

    for name, content in files.items():
        (input_dir / name).write_text(content)

    # Process all files
    stats = processor.process_all()

    # Verify all files were processed
    assert stats["files_processed"] == 3
    assert stats["files_errored"] == 0

    # Check output files
    for name, content in files.items():
        output_file = temp_workspace / "output" / name
        assert output_file.exists()
        assert output_file.read_text() == content

def test_markdown_with_document_reference(temp_workspace, processor):
    """Test markdown processing with a document reference."""
    input_dir = temp_workspace / "input"
    (input_dir / "attachments").mkdir()

    # Create a fake document file
    doc_path = input_dir / "attachments" / "test.docx"
    with open(doc_path, "wb") as f:
        f.write(b"fake docx data")  # Minimal fake document data

    # Create markdown with document reference
    md_content = "# Test\n[Test Document](attachments/test.docx)"
    (input_dir / "test.md").write_text(md_content)

    # Process files
    stats = processor.process_all()

    # Verify processing occurred
    assert stats["files_processed"] == 1
    assert stats["total_attachments"] >= 1

def test_error_handling(temp_workspace, processor):
    """Test error handling for invalid files and references."""
    input_dir = temp_workspace / "input"

    # Create markdown with invalid reference
    md_content = "# Test\n[Missing File](attachments/missing.doc)"
    (input_dir / "test.md").write_text(md_content)

    # Process files
    stats = processor.process_all()

    # Verify error handling
    assert stats["files_processed"] == 1
    assert stats["error_attachments"] >= 1

    # Check output contains error message
    output_file = temp_workspace / "output" / "test.md"
    assert output_file.exists()
    content = output_file.read_text()
    assert "Error" in content or "error" in content

def test_incremental_processing(temp_workspace, processor):
    """Test that only modified files are processed on subsequent runs."""
    input_dir = temp_workspace / "input"

    # Initial file
    doc1 = input_dir / "doc1.md"
    doc1.write_text("# Document 1\nInitial content")

    # First processing
    stats1 = processor.process_all()
    assert stats1["files_processed"] == 1

    # Run again without changes
    stats2 = processor.process_all()
    assert stats2["files_unchanged"] == 1
    assert stats2["files_processed"] == 0

    # Modify file and process again
    doc1.write_text("# Document 1\nModified content")
    stats3 = processor.process_all()
    assert stats3["files_processed"] == 1
    assert stats3["files_unchanged"] == 0

