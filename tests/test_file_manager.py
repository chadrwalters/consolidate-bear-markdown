"""Tests for file management functionality."""

import pytest
from pathlib import Path
import urllib.parse
from src.file_manager import FileManager


@pytest.fixture
def file_manager(tmp_path: Path) -> FileManager:
    """Create a file manager for testing."""
    return FileManager(
        cbm_dir=tmp_path / ".cbm",
        src_dir=tmp_path / "src",
        dest_dir=tmp_path / "dest"
    )


def test_init(file_manager: FileManager, tmp_path: Path) -> None:
    """Test file manager initialization."""
    assert (tmp_path / ".cbm" / "images").exists()
    assert (tmp_path / ".cbm" / "temp").exists()


def test_get_stable_path(file_manager: FileManager, tmp_path: Path) -> None:
    """Test getting stable paths for files."""
    # Test with a simple file path
    file_path = tmp_path / "src" / "test.jpg"
    stable_path = file_manager.get_stable_path(file_path)
    assert stable_path.parent == tmp_path / ".cbm" / "images"
    assert stable_path.name == "test.jpg"

    # Test with a nested path
    nested_path = tmp_path / "src" / "notes" / "images" / "test.jpg"
    stable_path = file_manager.get_stable_path(nested_path)
    assert stable_path.parent == tmp_path / ".cbm" / "images"
    assert stable_path.name == "notes_images_test.jpg"

    # Test with custom subdirectory
    custom_path = file_manager.get_stable_path(file_path, subdir="custom")
    assert custom_path.parent == tmp_path / ".cbm" / "custom"
    assert custom_path.name == "test.jpg"


def test_track_and_release_file(file_manager: FileManager, tmp_path: Path) -> None:
    """Test file tracking and release."""
    # Create test files
    file_path = tmp_path / "test.jpg"
    dependent = tmp_path / "doc.md"
    file_path.touch()
    dependent.touch()

    # Test tracking
    file_manager.track_file(file_path, dependent)
    assert str(file_path) in file_manager.resources
    assert file_manager.resources[str(file_path)].reference_count == 1
    assert dependent in file_manager.resources[str(file_path)].dependent_files

    # Test tracking same file again
    file_manager.track_file(file_path, dependent)
    assert file_manager.resources[str(file_path)].reference_count == 2

    # Test release
    file_manager.release_file(file_path, dependent)
    assert file_manager.resources[str(file_path)].reference_count == 1
    file_manager.release_file(file_path, dependent)
    assert str(file_path) not in file_manager.resources  # Should be removed when count reaches 0


def test_temporary_file_cleanup(file_manager: FileManager, tmp_path: Path) -> None:
    """Test cleanup of temporary files."""
    # Create test files
    temp_file = tmp_path / "temp.txt"
    perm_file = tmp_path / "perm.txt"
    temp_file.touch()
    perm_file.touch()

    # Track files
    file_manager.track_file(temp_file, is_temporary=True)
    file_manager.track_file(perm_file, is_temporary=False)

    # Release files
    file_manager.release_file(temp_file)
    file_manager.release_file(perm_file)

    # Check results
    assert not temp_file.exists()  # Temporary file should be deleted
    assert perm_file.exists()  # Permanent file should remain


def test_normalize_path(file_manager: FileManager, tmp_path: Path) -> None:
    """Test path normalization."""
    # Test with URL-encoded path
    encoded = "test%20file.jpg"
    normalized = file_manager.normalize_path(encoded)
    assert normalized == Path("test file.jpg")

    # Test with special characters
    special = "test<file>.jpg"
    normalized = file_manager.normalize_path(special)
    assert normalized == Path("testfile.jpg")

    # Test with existing file
    existing = tmp_path / "test.txt"
    existing.touch()
    normalized = file_manager.normalize_path(existing)
    assert normalized == existing.resolve()


def test_translate_path(file_manager: FileManager, tmp_path: Path) -> None:
    """Test path translation for markdown files."""
    # Test with path in .cbm directory
    cbm_path = tmp_path / ".cbm" / "images" / "test.jpg"
    translated = file_manager.translate_path(cbm_path)
    assert str(translated) == "../cbm/images/test.jpg"

    # Test with path outside .cbm
    other_path = tmp_path / "other" / "test.jpg"
    translated = file_manager.translate_path(other_path)
    assert translated == other_path


def test_validate_path(file_manager: FileManager, tmp_path: Path) -> None:
    """Test path validation."""
    # Create test files and directories
    src_file = tmp_path / "src" / "test.txt"
    src_file.parent.mkdir(parents=True)
    src_file.touch()

    outside_file = tmp_path / "outside" / "test.txt"
    outside_file.parent.mkdir(parents=True)
    outside_file.touch()

    # Test valid path
    assert file_manager.validate_path(src_file)

    # Test non-existent path
    assert not file_manager.validate_path(tmp_path / "nonexistent.txt")

    # Test path outside allowed directories
    assert not file_manager.validate_path(outside_file)

    # Test inaccessible path
    inaccessible = tmp_path / "noaccess"
    inaccessible.mkdir(mode=0o000)
    try:
        assert not file_manager.validate_path(inaccessible)
    finally:
        inaccessible.chmod(0o755)  # Restore permissions for cleanup


def test_cleanup(file_manager: FileManager, tmp_path: Path) -> None:
    """Test cleanup functionality."""
    # Create test files
    temp_files = [tmp_path / f"temp{i}.txt" for i in range(3)]
    for file in temp_files:
        file.touch()
        file_manager.track_file(file, is_temporary=True)

    # Create some files in temp directory
    temp_file = file_manager.temp_dir / "test.tmp"
    temp_file.touch()

    # Run cleanup
    file_manager.cleanup()

    # Verify cleanup
    for file in temp_files:
        assert not file.exists()
    assert not temp_file.exists()
    assert not file_manager.resources
