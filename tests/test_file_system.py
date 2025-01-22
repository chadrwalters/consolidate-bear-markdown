"""Tests for file system operations."""

from pathlib import Path

import pytest

from src.file_system import FileSystem


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
    # Create mock iCloud directory structure
    icloud_base = tmp_path / "Library/Mobile Documents/com~apple~CloudDocs"
    icloud_base.mkdir(parents=True)
    icloud_docs = icloud_base / "Documents"
    icloud_docs.mkdir()
    test_file = icloud_docs / "notes.md"
    test_file.touch()

    # Create mock Google Drive directory structure
    gdrive_base = tmp_path / "Library/CloudStorage/GoogleDrive-user@gmail.com/My Drive"
    gdrive_base.mkdir(parents=True)
    gdrive_docs = gdrive_base / "Documents"
    gdrive_docs.mkdir()
    gdrive_file = gdrive_docs / "notes.md"
    gdrive_file.touch()

    # Test iCloud path
    path = str(tmp_path / "iCloud Drive/Documents/notes.md")
    normalized = fs.normalize_cloud_path(path, test_root=tmp_path)
    assert "Library/Mobile Documents/com~apple~CloudDocs" in str(normalized)
    assert normalized.exists()

    # Test Google Drive path
    path = str(tmp_path / "Google Drive/Documents/notes.md")
    normalized = fs.normalize_cloud_path(path, test_root=tmp_path)
    assert "Library/CloudStorage/GoogleDrive-" in str(normalized)
    assert normalized.exists()

    # Test regular path
    path = str(tmp_path / "Documents/notes.md")
    normalized = fs.normalize_cloud_path(path, test_root=tmp_path)
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
