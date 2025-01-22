"""Tests for image caching functionality."""

from pathlib import Path

import pytest

from src.image_cache import ImageCache


@pytest.fixture
def image_cache(tmp_path: Path) -> ImageCache:
    """Create a test image cache."""
    return ImageCache(cbm_dir=tmp_path)


def test_cache_analysis(image_cache: ImageCache, tmp_path: Path) -> None:
    """Test image analysis caching functionality."""
    # Create test image
    test_image = tmp_path / "test.jpg"
    test_image.write_bytes(b"test image data")

    # Cache analysis
    analysis = "Test analysis result"
    image_cache.cache_analysis(test_image, analysis)

    # Verify cache
    cached_path = image_cache.get_cached_path(test_image)
    assert cached_path is not None
    assert cached_path.read_text() == analysis


def test_get_cached_path(image_cache: ImageCache, tmp_path: Path) -> None:
    """Test retrieving cached analysis paths."""
    # Create test image
    test_image = tmp_path / "test.jpg"
    test_image.write_bytes(b"test image data")

    # Initially should return None
    assert image_cache.get_cached_path(test_image) is None

    # Cache analysis and verify path
    analysis = "Test analysis"
    image_cache.cache_analysis(test_image, analysis)
    cached_path = image_cache.get_cached_path(test_image)
    assert cached_path is not None
    assert cached_path.exists()


def test_is_processed(image_cache: ImageCache, tmp_path: Path) -> None:
    """Test tracking processed images."""
    # Create test image
    test_image = tmp_path / "test.jpg"
    test_image.write_bytes(b"test image data")

    # Initially should not be processed
    assert not image_cache.is_processed(test_image)

    # Cache analysis and verify processed
    image_cache.cache_analysis(test_image, "Test analysis")
    assert image_cache.is_processed(test_image)


def test_cleanup(image_cache: ImageCache, tmp_path: Path) -> None:
    """Test cleanup functionality."""
    # Create and cache test images
    test_image1 = tmp_path / "test1.jpg"
    test_image2 = tmp_path / "test2.jpg"
    test_image1.write_bytes(b"test image 1")
    test_image2.write_bytes(b"test image 2")

    image_cache.cache_analysis(test_image1, "Analysis 1")
    image_cache.cache_analysis(test_image2, "Analysis 2")

    # Verify files exist
    cached_path1 = image_cache.get_cached_path(test_image1)
    cached_path2 = image_cache.get_cached_path(test_image2)
    assert cached_path1 is not None and cached_path1.exists()
    assert cached_path2 is not None and cached_path2.exists()

    # Cleanup and verify
    image_cache.cleanup()
    assert image_cache.get_cached_path(test_image1) is None
    assert image_cache.get_cached_path(test_image2) is None
    assert not image_cache.cache_dir.exists()


def test_error_handling(image_cache: ImageCache, tmp_path: Path) -> None:
    """Test error handling in cache operations."""
    # Test with non-existent file
    non_existent = tmp_path / "nonexistent.jpg"
    assert image_cache.get_cached_path(non_existent) is None
    assert not image_cache.is_processed(non_existent)
