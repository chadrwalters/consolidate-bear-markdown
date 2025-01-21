"""Image caching and deduplication."""

import hashlib
import logging
from pathlib import Path
from typing import Dict, Optional, Set

logger = logging.getLogger(__name__)


class ImageCache:
    """Handles image caching and deduplication."""

    def __init__(self, cbm_dir: Path) -> None:
        """Initialize the image cache.

        Args:
            cbm_dir: Directory for system files and processing
        """
        self.cbm_dir = Path(cbm_dir)
        self.cache_dir = self.cbm_dir / "image_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._hash_map: Dict[str, Path] = {}
        self._processed_images: Set[str] = set()

    def get_cached_path(self, image_path: Path) -> Optional[Path]:
        """Get the cached path for an image if it exists.

        Args:
            image_path: Path to the original image

        Returns:
            Path to the cached image if it exists, None otherwise
        """
        try:
            image_hash = self._compute_hash(image_path)
            return self._hash_map.get(image_hash)
        except Exception as e:
            logger.warning(f"Failed to get cached path for {image_path}: {e}")
            return None

    def cache_image(self, image_path: Path) -> Optional[Path]:
        """Cache an image and return its cached path.

        Args:
            image_path: Path to the image to cache

        Returns:
            Path to the cached image
        """
        try:
            image_hash = self._compute_hash(image_path)
            if image_hash in self._hash_map:
                return self._hash_map[image_hash]

            # Create cached file with hash as name
            cached_path = self.cache_dir / f"{image_hash}{image_path.suffix}"
            if not cached_path.exists():
                cached_path.write_bytes(image_path.read_bytes())

            self._hash_map[image_hash] = cached_path
            return cached_path

        except Exception as e:
            logger.error(f"Failed to cache image {image_path}: {e}")
            return None

    def is_processed(self, image_path: Path) -> bool:
        """Check if an image has been processed.

        Args:
            image_path: Path to the image

        Returns:
            True if the image has been processed, False otherwise
        """
        try:
            image_hash = self._compute_hash(image_path)
            return image_hash in self._processed_images
        except Exception:
            return False

    def mark_processed(self, image_path: Path) -> None:
        """Mark an image as processed.

        Args:
            image_path: Path to the image
        """
        try:
            image_hash = self._compute_hash(image_path)
            self._processed_images.add(image_hash)
        except Exception as e:
            logger.warning(f"Failed to mark image as processed {image_path}: {e}")

    def _compute_hash(self, file_path: Path) -> str:
        """Compute SHA-256 hash of a file.

        Args:
            file_path: Path to the file

        Returns:
            Hex digest of the file's SHA-256 hash
        """
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def cleanup(self) -> None:
        """Clean up cached files."""
        try:
            if self.cache_dir.exists():
                for file in self.cache_dir.iterdir():
                    try:
                        file.unlink()
                    except Exception as e:
                        logger.warning(f"Failed to delete cached file {file}: {e}")
                self.cache_dir.rmdir()
        except Exception as e:
            logger.error(f"Error cleaning up cache directory: {e}")

    def __del__(self) -> None:
        """Clean up on object deletion."""
        self.cleanup()
