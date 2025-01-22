"""Image analysis caching functionality."""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class ImageCache:
    """Cache for image analysis results."""

    def __init__(self, cbm_dir: Path) -> None:
        """Initialize the image cache.

        Args:
            cbm_dir: Directory for system files and processing
        """
        self.cache_dir = Path(cbm_dir) / "image_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def is_processed(self, image_path: Path) -> bool:
        """Check if an image has been processed.

        Args:
            image_path: Path to the image file

        Returns:
            True if the image has been processed, False otherwise
        """
        cache_path = self._get_cache_path(image_path)
        return cache_path.exists()

    def get_cached_path(self, image_path: Path) -> Optional[Path]:
        """Get the path to the cached analysis.

        Args:
            image_path: Path to the image file

        Returns:
            Path to the cached analysis file, or None if not found
        """
        cache_path = self._get_cache_path(image_path)
        return cache_path if cache_path.exists() else None

    def cache_analysis(self, image_path: Path, analysis: str) -> None:
        """Cache the analysis result.

        Args:
            image_path: Path to the image file
            analysis: Analysis text to cache
        """
        cache_path = self._get_cache_path(image_path)
        cache_path.write_text(analysis)

    def _get_cache_path(self, image_path: Path) -> Path:
        """Get the cache file path for an image.

        Args:
            image_path: Path to the image file

        Returns:
            Path where the cache file should be stored
        """
        # Use hash of absolute path as cache key
        cache_key = str(image_path.resolve()).__hash__()
        return self.cache_dir / f"{cache_key}.txt"

    def cleanup(self) -> None:
        """Clean up cache files."""
        try:
            if self.cache_dir.exists():
                for file in self.cache_dir.iterdir():
                    try:
                        file.unlink()
                    except Exception as e:
                        logger.warning(f"Failed to delete cache file {file}: {e}")
                self.cache_dir.rmdir()
        except Exception as e:
            logger.warning(f"Error cleaning up cache directory: {e}")
