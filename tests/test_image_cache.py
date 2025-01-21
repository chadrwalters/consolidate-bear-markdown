"""Tests for image caching functionality."""

import hashlib
from pathlib import Path
import pytest

from src.image_cache import ImageCache


@pytest.fixture
def image_cache(tmp_path: Path) -> ImageCache:
    """Create an ImageCache instance for testing."""
    return ImageCache(tmp_path)


def test_cache_image(image_cache: ImageCache, tmp_path: Path) -> None:
    """Test image caching functionality."""
    # Create test image
    test_image = tmp_path / "test.jpg"
    test_image.write_bytes(b"test image data")

    # Cache the image
    cached_path = image_cache.cache_image(test_image)
    assert cached_path is not None
    assert cached_path.exists()
    assert cached_path.read_bytes() == b"test image data"

    # Try caching the same image again
    cached_path2 = image_cache.cache_image(test_image)
    assert cached_path2 == cached_path  # Should return the same path


def test_get_cached_path(image_cache: ImageCache, tmp_path: Path) -> None:
    """Test retrieving cached image paths."""
    # Create test image
    test_image = tmp_path / "test.jpg"
    test_image.write_bytes(b"test image data")

    # Initially should return None
    assert image_cache.get_cached_path(test_image) is None

    # Cache the image
    cached_path = image_cache.cache_image(test_image)
    assert cached_path is not None

    # Should now return the cached path
    retrieved_path = image_cache.get_cached_path(test_image)
    assert retrieved_path == cached_path


def test_is_processed(image_cache: ImageCache, tmp_path: Path) -> None:
    """Test tracking processed images."""
    # Create test image
    test_image = tmp_path / "test.jpg"
    test_image.write_bytes(b"test image data")

    # Initially should not be processed
    assert not image_cache.is_processed(test_image)

    # Mark as processed
    image_cache.mark_processed(test_image)
    assert image_cache.is_processed(test_image)


def test_cleanup(image_cache: ImageCache, tmp_path: Path) -> None:
    """Test cleanup functionality."""
    # Create and cache test images
    test_image1 = tmp_path / "test1.jpg"
    test_image2 = tmp_path / "test2.jpg"
    test_image1.write_bytes(b"test image 1")
    test_image2.write_bytes(b"test image 2")

    cached_path1 = image_cache.cache_image(test_image1)
    cached_path2 = image_cache.cache_image(test_image2)

    assert cached_path1 is not None and cached_path1.exists()
    assert cached_path2 is not None and cached_path2.exists()

    # Clean up
    image_cache.cleanup()

    # Verify files are cleaned up
    assert not cached_path1.exists()
    assert not cached_path2.exists()
    assert not image_cache.cache_dir.exists()


def test_hash_computation(image_cache: ImageCache, tmp_path: Path) -> None:
    """Test hash computation for images."""
    # Create test image
    test_image = tmp_path / "test.jpg"
    image_data = b"test image data"
    test_image.write_bytes(image_data)

    # Compute hash manually
    sha256_hash = hashlib.sha256()
    sha256_hash.update(image_data)
    expected_hash = sha256_hash.hexdigest()

    # Cache the image and extract hash from path
    cached_path = image_cache.cache_image(test_image)
    assert cached_path is not None
    actual_hash = cached_path.stem

    assert actual_hash == expected_hash


def test_error_handling(image_cache: ImageCache, tmp_path: Path) -> None:
    """Test error handling in cache operations."""
    # Test with non-existent file
    non_existent = tmp_path / "nonexistent.jpg"
    assert image_cache.get_cached_path(non_existent) is None
    assert image_cache.cache_image(non_existent) is None
    assert not image_cache.is_processed(non_existent)

    # Test with invalid file
    invalid_file = tmp_path / "invalid.jpg"
    invalid_file.write_text("not an image")
    cached_path = image_cache.cache_image(invalid_file)
    assert cached_path is not None  # Should still cache even if not a valid image
    assert cached_path.exists()
    assert cached_path.read_text() == "not an image"
