# mypy: ignore-errors
"""Tests for the simplified markdown processor."""

from pathlib import Path
from typing import Any, Dict, Generator, Optional, cast, Callable, Protocol, List, TypeVar, runtime_checkable, Union, NoReturn
from unittest.mock import Mock, patch, MagicMock, create_autospec

import pytest
import os
import time
from openai import OpenAI

from src.converter_factory import ConverterFactory
from src.file_manager import FileManager
from src.file_system import FileSystem, MarkdownFile
from src.markdown_processor_v2 import MarkdownProcessorV2, AttachmentProcessingResult, ConversionResult


T = TypeVar('T')


@runtime_checkable
class ConverterCallable(Protocol):
    """Protocol for converter callable objects."""
    def __call__(self, path: Path) -> ConversionResult: ...
    def return_value(self) -> ConversionResult: ...
    def side_effect(self, func: Callable[[Path], ConversionResult]) -> None: ...


def create_mock_method(return_value: T) -> Mock:
    """Create a mock method with a return value."""
    mock = Mock()
    mock.return_value = return_value  # type: ignore
    return mock


@pytest.fixture
def mock_converter_factory() -> Mock:
    """Create a mock ConverterFactory."""
    mock = Mock(spec=ConverterFactory)
    mock.convert_file = Mock()  # type: ignore
    mock.convert_file.return_value = cast(ConversionResult, {  # type: ignore
        "success": True,
        "content": "Converted content",
        "error": None,
        "text_content": "Text content",
        "text": "Text",
        "type": "document",
    })
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
    mock.get_attachments = create_mock_method([])
    mock.get_attachments.side_effect = lambda p: list(p.glob("*")) if p.exists() else []  # type: ignore
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
    fs.discover_markdown_files = create_mock_method([])
    fs.get_attachments = create_mock_method([])
    fs.get_attachments.side_effect = lambda p: list(p.glob("*")) if p.exists() else []

    # Set up converter factory with default success response
    converter_factory = Mock(spec=ConverterFactory)
    converter_factory.converters = {}  # Add this to prevent cleanup errors
    converter_factory.convert_file = create_mock_method(cast(ConversionResult, {
        "success": True,
        "content": "Converted content",
        "error": None,
        "text_content": "Text content",
        "text": "Text",
        "type": "text",
    }))

    processor = MarkdownProcessorV2(
        converter_factory=converter_factory,
        file_system=fs,
        src_dir=src_dir,
        dest_dir=dest_dir,
    )
    return processor


class MockConverter:
    """Mock converter class for testing."""
    def __init__(self, return_value: Optional[ConversionResult] = None) -> None:
        self._return_value = return_value or cast(ConversionResult, {
            "success": True,
            "content": "Converted content",
            "error": None,
            "text_content": "Text content",
            "text": "Text",
            "type": "document",
        })
        self._side_effect: Optional[Callable[[Path], ConversionResult]] = None
        self._called = False

    def __call__(self, path: Path) -> ConversionResult:
        self._called = True
        if self._side_effect is not None:
            return self._side_effect(path)
        return self._return_value

    def assert_not_called(self) -> None:
        """Assert the converter was not called."""
        assert not self._called, "Expected converter not to be called"

    @property
    def side_effect(self) -> Optional[Callable[[Path], ConversionResult]]:
        """Get the side effect function."""
        return self._side_effect

    @side_effect.setter
    def side_effect(self, func: Optional[Callable[[Path], ConversionResult]]) -> None:
        """Set the side effect function."""
        self._side_effect = func


def test_process_attachment_success(processor: MarkdownProcessorV2) -> None:
    """Test successful attachment processing."""
    # Create test files in src directory
    src_file = processor.src_dir / "test.md"
    src_file.parent.mkdir(parents=True, exist_ok=True)
    src_file.write_text("test")

    attachment_path = processor.src_dir / "test.jpg"
    attachment_path.write_text("fake image")

    # Set up mock to return success
    mock_converter = MockConverter()
    processor.converter_factory.convert_file = mock_converter  # type: ignore

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

    # Set up mock converter
    mock_converter = MockConverter()
    processor.converter_factory.convert_file = mock_converter  # type: ignore

    result = processor.process_attachment(src_file, attachment_path)
    assert result["success"] is False
    assert result["error"] is not None
    assert "not found" in str(result["error"])

    mock_converter.assert_not_called()


def test_process_attachment_conversion_error(processor: MarkdownProcessorV2) -> None:
    """Test processing an attachment that fails conversion."""
    src_file = processor.src_dir / "test.md"
    src_file.write_text("test content")

    attachment_path = processor.src_dir / "test.jpg"
    attachment_path.write_text("fake image")

    # Set up mock to return error
    processor.converter_factory.convert_file = create_mock_method(cast(ConversionResult, {  # type: ignore
        "success": False,
        "error": "Conversion failed",
        "error_type": "conversion_error",
        "text": None,
        "text_content": None,
        "content": None,
        "type": None,
    }))

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

    processor.converter_factory.convert_file.return_value = cast(ConversionResult, {  # type: ignore
        "success": True,
        "content": "Converted content",
        "error": None,
        "text_content": "Text content",
        "text": "Text",
        "type": "document",
    })

    result = processor.process_markdown_file(md_file)
    assert result is not None
    assert "success_attachments" in result
    assert result["success_attachments"] == 2


def test_should_process_force_generation(processor: MarkdownProcessorV2) -> bool:
    """Test should_process with force_generation enabled."""
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
    return processor.should_process(md_file) is True


def test_should_process_new_file(processor: MarkdownProcessorV2) -> bool:
    """Test should_process with a new file."""
    # Create a test file in src_dir
    src_file = processor.src_dir / "test.md"
    src_file.parent.mkdir(parents=True, exist_ok=True)
    src_file.write_text("test")

    md_file = MarkdownFile(
        md_path=src_file,
        attachment_dir=None
    )

    # Should return True for new files
    return processor.should_process(md_file) is True


def test_should_process_modified_markdown(processor: MarkdownProcessorV2) -> bool:
    """Test should_process with a modified markdown file."""
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
    return processor.should_process(md_file) is True


def test_should_process_modified_attachment(processor: MarkdownProcessorV2) -> bool:
    """Test should_process with a modified attachment."""
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
    return processor.should_process(md_file) is True


def test_should_process_unmodified(processor: MarkdownProcessorV2) -> bool:
    """Test should_process with an unmodified file."""
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
    return processor.should_process(md_file) is False


def test_hero_single_file_single_attachment(processor: MarkdownProcessorV2) -> None:
    """Test processing a single file with a single attachment."""
    # Create test files in src directory
    src_file = processor.src_dir / "test.md"
    src_file.parent.mkdir(parents=True, exist_ok=True)

    attach_dir = processor.src_dir / "test"
    attach_dir.mkdir()

    # Create test image
    image_path = attach_dir / "image.jpg"
    image_path.write_text("fake image")

    # Create markdown content with a single image reference
    content = """
    # Test Document

    Here is an important image:
    ![Test Image](image.jpg)<!-- {"embed": true} -->

    Some text after the image.
    """
    src_file.write_text(content)

    # Set up mock converter to return specific content
    processor.converter_factory.convert_file.return_value = {  # type: ignore
        "success": True,
        "content": "![Converted Image](data:image/jpeg;base64,ABC123)",
        "error": None,
        "text_content": "A picture of a test image",
        "text": "Test image description",
        "type": "image",
    }

    # Process the file
    md_file = MarkdownFile(
        md_path=src_file,
        attachment_dir=attach_dir
    )

    result = processor.process_markdown_file(md_file)

    # Verify the result
    assert result is not None
    assert result["success_attachments"] == 1
    assert result["error_attachments"] == 0
    assert result["skipped_attachments"] == 0

    # Check the output file exists and contains the converted content
    out_file = processor.dest_dir / "test.md"
    assert out_file.exists()

    content = out_file.read_text()
    assert "![Converted Image](data:image/jpeg;base64,ABC123)" in content
    assert "Some text after the image" in content  # Original text preserved

    # Verify final stats
    stats = processor.stats.get_statistics()
    assert stats["files_processed"] == 1
    assert stats["success_attachments"] == 1
    assert stats["error_attachments"] == 0
    assert stats["skipped_attachments"] == 0


def test_hero_single_file_multiple_attachments(processor: MarkdownProcessorV2) -> None:
    """Test processing a single file with multiple attachments."""
    # Create test files in src directory
    src_file = processor.src_dir / "test.md"
    src_file.parent.mkdir(parents=True, exist_ok=True)

    attach_dir = processor.src_dir / "test"
    attach_dir.mkdir()

    # Create only the valid image file
    image_path = attach_dir / "valid.jpg"
    image_path.write_text("fake image")

    # Create markdown content with multiple references
    content = """
    # Test Document with Multiple Attachments

    1. Valid image:
    ![Valid Image](valid.jpg)<!-- {"embed": true} -->

    2. External URL:
    ![External Image](https://example.com/image.jpg)<!-- {"embed": true} -->

    3. Missing file:
    ![Missing Image](missing.jpg)<!-- {"embed": true} -->
    """
    src_file.write_text(content)

    # Configure mock converter with different responses
    def convert_impl(file_path: Path) -> ConversionResult:
        if str(file_path).endswith("valid.jpg"):
            return cast(ConversionResult, {
                "success": True,
                "error": None,
                "error_type": None,
                "text": "Valid image",
                "text_content": "A valid image",
                "content": "![Valid Converted](data:image/jpeg;base64,VALID123)",
                "type": "image"
            })
        elif "example.com" in str(file_path):
            return cast(ConversionResult, {
                "success": False,
                "error": "External URLs are not supported",
                "error_type": "external_url",
                "text": None,
                "text_content": None,
                "content": None,
                "type": None
            })
        else:
            return cast(ConversionResult, {
                "success": False,
                "error": "File not found",
                "error_type": "file_not_found",
                "text": None,
                "text_content": None,
                "content": None,
                "type": None
            })

    mock_converter = MockConverter()
    mock_converter.side_effect = convert_impl  # type: ignore
    processor.converter_factory.convert_file = mock_converter  # type: ignore

    # Process the file
    md_file = MarkdownFile(
        md_path=src_file,
        attachment_dir=attach_dir
    )

    result = processor.process_markdown_file(md_file)

    # Verify the result
    assert result is not None
    assert result["success_attachments"] == 1
    assert result["error_attachments"] == 1
    assert result["skipped_attachments"] == 1

    # Check the output file
    out_file = processor.dest_dir / "test.md"
    assert out_file.exists()

    content = out_file.read_text()
    # Valid image was converted
    assert "![Valid Converted](data:image/jpeg;base64,VALID123)" in content
    # External URL was skipped with comment
    assert "![External Image](https://example.com/image.jpg)" in content
    assert "<!-- Error: External URL skipped -->" in content
    # Missing file has error comment
    assert "![Missing Image](missing.jpg)" in content
    assert "<!-- File not found -->" in content

    # Verify final stats
    stats = processor.stats.get_statistics()
    assert stats["files_processed"] == 1
    assert stats["success_attachments"] == 1
    assert stats["error_attachments"] == 1
    assert stats["skipped_attachments"] == 1


def test_hero_file_no_references(processor: MarkdownProcessorV2) -> None:
    """Test processing a file with no references."""
    # Create test files in src directory
    src_file = processor.src_dir / "test.md"
    src_file.parent.mkdir(parents=True, exist_ok=True)

    # Create markdown content with no references
    content = """
    # Plain Document

    This is a simple markdown file with:
    - No image references
    - No link references
    - Just plain text and formatting

    ## Section 1
    Regular paragraph text.

    ## Section 2
    More regular text with *formatting* and **bold**.
    """
    src_file.write_text(content)

    # Process the file
    md_file = MarkdownFile(
        md_path=src_file,
        attachment_dir=None  # No attachment dir needed
    )

    result = processor.process_markdown_file(md_file)

    # Verify the result
    assert result is not None
    assert result["success_attachments"] == 0
    assert result["error_attachments"] == 0
    assert result["skipped_attachments"] == 0

    # Check the output file
    out_file = processor.dest_dir / "test.md"
    assert out_file.exists()

    # Content should be identical
    assert out_file.read_text() == content

    # Verify final stats
    stats = processor.stats.get_statistics()
    assert stats["files_processed"] == 1
    assert stats["files_unchanged"] == 1
    assert stats["success_attachments"] == 0
    assert stats["error_attachments"] == 0
    assert stats["skipped_attachments"] == 0

    # Verify converter was never called
    processor.converter_factory.convert_file.assert_not_called()


def test_hero_smart_regeneration(processor: MarkdownProcessorV2) -> None:
    """Test smart regeneration of files."""
    # Create test files in src directory
    src_file = processor.src_dir / "test.md"
    src_file.parent.mkdir(parents=True, exist_ok=True)

    attach_dir = processor.src_dir / "test"
    attach_dir.mkdir()

    # Create a test image
    image_path = attach_dir / "image.jpg"
    image_path.write_text("fake image")

    # Create markdown content
    content = """
    # Test Document

    ![Test Image](image.jpg)<!-- {"embed": true} -->
    """
    src_file.write_text(content)

    # Create output file
    out_file = processor.dest_dir / "test.md"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(content)

    # Create MarkdownFile object
    md_file = MarkdownFile(
        md_path=src_file,
        attachment_dir=attach_dir
    )

    # Test 1: Force generation always processes
    processor.force_generation = True
    assert processor.should_process(md_file) is True

    # Test 2: Skip if output is newer
    processor.force_generation = False
    # Make output file newer than source and attachment
    now = time.time()
    os.utime(src_file, (now - 100, now - 100))
    os.utime(image_path, (now - 100, now - 100))
    os.utime(out_file, (now, now))
    assert processor.should_process(md_file) is False

    # Test 3: Process if source is newer than output
    os.utime(src_file, (now + 100, now + 100))
    assert processor.should_process(md_file) is True

    # Test 4: Process if attachment is newer than output
    os.utime(src_file, (now - 100, now - 100))
    os.utime(image_path, (now + 100, now + 100))
    assert processor.should_process(md_file) is True

    # Test 5: Skip if attachment dir is absent
    md_file = MarkdownFile(
        md_path=src_file,
        attachment_dir=None
    )
    assert processor.should_process(md_file) is False

    # Verify stats reflect skipped files
    stats = processor.stats.get_statistics()
    assert "files_skipped" in stats


def test_hero_process_all_mixed_files(processor: MarkdownProcessorV2) -> None:
    """Test processing a mix of files."""
    # Create test files in src directory
    def create_test_file(name: str, content: str, has_attach_dir: bool = False) -> tuple[Path, Path, MarkdownFile]:
        src_file = processor.src_dir / name
        src_file.parent.mkdir(parents=True, exist_ok=True)
        src_file.write_text(content)

        attach_dir = None
        if has_attach_dir:
            attach_dir = processor.src_dir / name.replace(".md", "")
            attach_dir.mkdir()

        md_file = MarkdownFile(
            md_path=src_file,
            attachment_dir=attach_dir if has_attach_dir else None
        )

        out_file = processor.dest_dir / name
        out_file.parent.mkdir(parents=True, exist_ok=True)

        return src_file, out_file, md_file

    # 1. File with successful attachment
    success_content = """
    # Success Document
    ![Valid Image](image.jpg)<!-- {"embed": true} -->
    """
    success_file, success_out, success_md = create_test_file("success.md", success_content, True)
    if success_md.attachment_dir:  # Add check for None
        (success_md.attachment_dir / "image.jpg").write_text("fake image")

    # 2. File with no attachments
    plain_content = """
    # Plain Document
    Just regular text.
    """
    plain_file, plain_out, plain_md = create_test_file("plain.md", plain_content)
    plain_out.write_text(plain_content)  # Pre-create output

    # 3. File with errors
    error_content = """
    # Error Document
    ![Missing](missing.jpg)<!-- {"embed": true} -->
    """
    error_file, error_out, error_md = create_test_file("error.md", error_content, True)

    # 4. File to be skipped (newer output)
    skip_content = """
    # Skip Document
    ![Skip](skip.jpg)<!-- {"embed": true} -->
    """
    skip_file, skip_out, skip_md = create_test_file("skip.md", skip_content, True)
    if skip_md.attachment_dir:  # Add check for None
        (skip_md.attachment_dir / "skip.jpg").write_text("fake image")
    skip_out.write_text("Already processed")

    # Make skip output newer than source
    now = time.time()
    os.utime(skip_file, (now - 100, now - 100))
    os.utime(skip_out, (now, now))

    # Configure mock converter with different responses
    def mock_convert(file_path: Path, *args: Any, **kwargs: Any) -> ConversionResult:
        if str(file_path).endswith("image.jpg"):
            return cast(ConversionResult, {
                "success": True,
                "content": "![Success](data:image/jpeg;base64,SUCCESS)",
                "error": None,
                "text_content": "Success image",
                "text": "Success",
                "type": "image"
            })
        elif str(file_path).endswith("missing.jpg"):
            return cast(ConversionResult, {
                "success": False,
                "error": "File not found",
                "error_type": "file_not_found",
                "text": None,
                "text_content": None
            })
        else:
            return cast(ConversionResult, {
                "success": True,
                "content": "![Generic](data:image/jpeg;base64,GENERIC)",
                "error": None,
                "text_content": "Generic image",
                "text": "Generic",
                "type": "image"
            })

    processor.converter_factory.convert_file.assert_not_called()  # type: ignore
    processor.converter_factory.convert_file.side_effect = mock_convert  # type: ignore
    processor.file_system.discover_markdown_files.return_value = [  # type: ignore
        success_md,
        plain_md,
        error_md,
        skip_md,
    ]

    processor.process_all()

    # Verify final stats
    stats = processor.stats.get_statistics()
    assert stats["files_processed"] == 3  # success, plain, error
    assert stats["files_skipped"] == 1    # skip
    assert stats["files_unchanged"] == 1   # plain
    assert stats["success_attachments"] == 1  # success file
    assert stats["error_attachments"] == 1    # error file

    # Check individual file results
    # 1. Success file
    assert success_out.exists()
    success_content = success_out.read_text()
    assert "![Success](data:image/jpeg;base64,SUCCESS)" in success_content

    # 2. Plain file - should be unchanged
    assert plain_out.exists()
    assert plain_out.read_text() == plain_content

    # 3. Error file
    assert error_out.exists()
    error_content = error_out.read_text()
    assert "![Missing](missing.jpg)" in error_content
    assert "<!-- File not found -->" in error_content

    # 4. Skip file - should retain original content
    assert skip_out.exists()
    assert skip_out.read_text() == "Already processed"
