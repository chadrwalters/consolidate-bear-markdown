"""Tests for file system operations."""

from pathlib import Path
import os

import pytest

from src.file_system import FileSystem, MarkdownFile


@pytest.fixture
def fs(tmp_path: Path) -> FileSystem:
    """Create FileSystem instance."""
    return FileSystem(
        cbm_dir=str(tmp_path / ".cbm"),
        src_dir=str(tmp_path / "src"),
        dest_dir=str(tmp_path / "dest"),
    )


def test_init(tmp_path: Path) -> None:
    """Test initialization."""
    cbm_dir = tmp_path / ".cbm"
    src_dir = tmp_path / "src"
    dest_dir = tmp_path / "dest"

    fs = FileSystem(cbm_dir=str(cbm_dir), src_dir=str(src_dir), dest_dir=str(dest_dir))
    assert fs.cbm_dir == cbm_dir
    assert fs.src_dir == src_dir
    assert fs.dest_dir == dest_dir
    assert cbm_dir.exists()


def test_normalize_cloud_path(fs: FileSystem, tmp_path: Path) -> None:
    """Test cloud path normalization."""
    # Create test directories
    icloud_dir = tmp_path / "Library/Mobile Documents/com~apple~CloudDocs/Documents"
    icloud_dir.mkdir(parents=True)
    icloud_file = icloud_dir / "notes.md"
    icloud_file.touch()

    gdrive_dir = tmp_path / "Library/CloudStorage/GoogleDrive-test/My Drive/Documents"
    gdrive_dir.mkdir(parents=True)
    gdrive_file = gdrive_dir / "notes.md"
    gdrive_file.touch()

    # Test iCloud path
    path = str(tmp_path / "iCloud Drive/Documents/notes.md")
    normalized = fs.normalize_cloud_path(path, test_root=tmp_path)
    if normalized is None:
        pytest.fail("Expected normalized path to not be None")
    assert "Library/Mobile Documents/com~apple~CloudDocs" in str(normalized)
    assert normalized.exists()

    # Test Google Drive path
    path = str(tmp_path / "Google Drive/Documents/notes.md")
    normalized = fs.normalize_cloud_path(path, test_root=tmp_path)
    if normalized is None:
        pytest.fail("Expected normalized path to not be None")
    assert "Library/CloudStorage/GoogleDrive-" in str(normalized)
    assert normalized.exists()

    # Test regular path
    path = str(tmp_path / "Documents/notes.md")
    normalized = fs.normalize_cloud_path(path, test_root=tmp_path)
    if normalized is None:
        pytest.fail("Expected normalized path to not be None")
    assert str(normalized) == str(Path(path).resolve())


def test_discover_markdown_files(fs: FileSystem, tmp_path: Path) -> None:
    """Test markdown file discovery."""
    # Create test directory structure
    notes_dir = tmp_path / "src" / "notes"
    notes_dir.mkdir(parents=True)

    # Create markdown file without attachments
    md1 = notes_dir / "note1.md"
    md1.write_text("test content")

    # Create markdown file with attachments
    md2 = notes_dir / "note2.md"
    md2.write_text("test content")
    md2_attachments = notes_dir / "note2"
    md2_attachments.mkdir()
    (md2_attachments / "image.jpg").write_bytes(b"fake image")

    # Test discovery
    files = list(fs.discover_markdown_files(notes_dir))
    assert len(files) == 2

    # Verify files were found
    file_paths = {str(f.md_path.name): f.attachment_dir for f in files}
    assert "note1.md" in file_paths
    assert "note2.md" in file_paths
    assert file_paths["note1.md"] is None
    assert file_paths["note2.md"] == md2_attachments

    # Test non-existent directory
    with pytest.raises(FileNotFoundError):
        list(fs.discover_markdown_files(tmp_path / "nonexistent"))


def test_get_attachments(fs: FileSystem, tmp_path: Path) -> None:
    """Test attachment retrieval."""
    # Create test attachment directory
    attach_dir = tmp_path / "attachments"
    attach_dir.mkdir()

    # Create some attachments
    files = ["a.jpg", "b.txt", "c.pdf"]
    for f in files:
        (attach_dir / f).write_text("test")

    # Create hidden file (should be ignored)
    (attach_dir / ".hidden").write_text("hidden")

    # Test attachment retrieval
    attachments = fs.get_attachments(attach_dir)
    assert len(attachments) == 3
    assert [a.name for a in attachments] == files

    # Test non-existent directory
    assert fs.get_attachments(tmp_path / "nonexistent") == []


def test_ensure_output_dir(fs: FileSystem, tmp_path: Path) -> None:
    """Test output directory creation."""
    # Create source file
    src_file = tmp_path / "src" / "notes" / "test.md"
    src_file.parent.mkdir(parents=True)
    src_file.write_text("test content")

    # Test creating output directory
    output_path = fs.ensure_output_dir(src_file)
    assert output_path.parent.exists()
    assert output_path.name == "test.md"
    assert output_path.parent == tmp_path / "dest" / "notes"


def test_attachment_resolution_with_url_encoded_paths(tmp_path: Path) -> None:
    """Test attachment resolution with URL encoded paths."""
    # Create test directory structure
    cloud_base = tmp_path / "Library/Mobile Documents/com~apple~CloudDocs/_NovaInput"
    cloud_base.mkdir(parents=True)

    # Create test markdown file and attachment directory with spaces
    md_dir = cloud_base / "20241230 - O1 and Cursor Demo"
    md_dir.mkdir(parents=True)
    md_file = md_dir / "20241230 - O1 and Cursor Demo.md"
    md_file.write_text("Test content")

    # Create attachment directory and file
    attachment_dir = md_dir / "20241230 - O1 and Cursor Demo"
    attachment_dir.mkdir()
    attachment_file = attachment_dir / "20241222 O1 and Cursor Demo.mov"
    attachment_file.write_text("Test video content")

    # Initialize FileSystem with test paths
    fs = FileSystem(
        src_dir=cloud_base,
        dest_dir=tmp_path / "output",
        cbm_dir=tmp_path / "cbm"
    )

    # Get the markdown file through discovery
    md_files = list(fs.discover_markdown_files())
    assert len(md_files) == 1
    md_obj = md_files[0]

    # Try to get the attachment using URL encoded path
    encoded_path = "20241230%20-%20O1%20and%20Cursor%20Demo/20241222%20O1%20and%20Cursor%20Demo.mov"
    attachment = md_obj.get_attachment(encoded_path)

    # Assert that we found the attachment
    assert attachment is not None, "Attachment should not be None"
    assert str(attachment).endswith("20241222 O1 and Cursor Demo.mov"), f"Unexpected attachment path: {attachment}"


def test_attachment_resolution_with_complex_paths(tmp_path: Path) -> None:
    """Test attachment resolution with complex paths."""
    # Create test directory structure with spaces and special characters
    cloud_base = tmp_path / "Library/Mobile Documents/com~apple~CloudDocs/_NovaInput"
    cloud_base.mkdir(parents=True)

    # Create nested directory structure with spaces
    md_dir = cloud_base / "20241230 - O1 and Cursor Demo"
    md_dir.mkdir(parents=True)

    # Create markdown file
    md_file = md_dir / "20241230 - O1 and Cursor Demo.md"
    md_file.write_text("Test content with reference to [[20241222 O1 and Cursor Demo.mov]]")

    # Create nested attachment directory
    attachment_dir = md_dir / "20241230 - O1 and Cursor Demo"
    attachment_dir.mkdir()

    # Create attachment file
    attachment_file = attachment_dir / "20241222 O1 and Cursor Demo.mov"
    attachment_file.write_text("Test video content")

    # Initialize FileSystem with test paths
    fs = FileSystem(
        src_dir=str(cloud_base),
        dest_dir=str(tmp_path / "output"),
        cbm_dir=str(tmp_path / "cbm")
    )

    # Get the markdown file through discovery
    md_files = list(fs.discover_markdown_files())
    assert len(md_files) == 1
    md_obj = md_files[0]

    # Test with various forms of URL encoded paths
    test_paths = [
        "20241230%20-%20O1%20and%20Cursor%20Demo/20241222%20O1%20and%20Cursor%20Demo.mov",
        "20241230 - O1 and Cursor Demo/20241222 O1 and Cursor Demo.mov",
        "20241230%20-%20O1%20and%20Cursor%20Demo/20241222 O1 and Cursor Demo.mov",
    ]

    for path in test_paths:
        attachment = md_obj.get_attachment(path)
        assert attachment is not None, f"Failed to resolve attachment path: {path}"
        assert str(attachment).endswith("20241222 O1 and Cursor Demo.mov"), f"Unexpected attachment path: {attachment}"

    # Test with non-existent file
    bad_path = "20241230%20-%20O1%20and%20Cursor%20Demo/nonexistent.mov"
    attachment = md_obj.get_attachment(bad_path)
    assert attachment is None, f"Expected None for non-existent path: {bad_path}"


def test_attachment_resolution_with_real_cloud_paths(tmp_path: Path) -> None:
    """Test attachment resolution with real cloud paths."""
    # Create test directory structure
    cloud_base = tmp_path / "Library/Mobile Documents/com~apple~CloudDocs/_NovaInput"
    cloud_base.mkdir(parents=True)

    # Create nested directory structure with spaces
    md_dir = cloud_base / "20241230 - O1 and Cursor Demo"
    md_dir.mkdir(parents=True)

    # Create markdown file
    md_file = md_dir / "20241230 - O1 and Cursor Demo.md"
    md_file.write_text("Test content with reference to [[20241222 O1 and Cursor Demo.mov]]")

    # Create attachment file directly in the markdown directory
    attachment_file = md_dir / "20241222 O1 and Cursor Demo.mov"
    attachment_file.write_text("Test video content")

    # Initialize FileSystem with test paths
    fs = FileSystem(
        src_dir=str(cloud_base),
        dest_dir=str(tmp_path / "output"),
        cbm_dir=str(tmp_path / "cbm")
    )

    # Get the markdown file through discovery
    md_files = list(fs.discover_markdown_files())
    assert len(md_files) == 1
    md_obj = md_files[0]

    # Test with URL encoded path
    encoded_path = "20241230%20-%20O1%20and%20Cursor%20Demo/20241222%20O1%20and%20Cursor%20Demo.mov"
    attachment = md_obj.get_attachment(encoded_path)
    assert attachment is not None, f"Failed to resolve attachment path: {encoded_path}"
    assert str(attachment).endswith("20241222 O1 and Cursor Demo.mov"), f"Unexpected attachment path: {attachment}"
    assert attachment.exists(), f"Attachment file not found: {attachment}"
