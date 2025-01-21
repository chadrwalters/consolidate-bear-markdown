"""Image format conversion and optimization."""

import logging
import os
import platform
import subprocess
import shutil
from pathlib import Path
from typing import Optional, Set
from PIL import Image

logger = logging.getLogger(__name__)


class ImageConverter:
    """Handles image format conversion and optimization."""

    def __init__(self, cbm_dir: str | Path) -> None:
        """Initialize the image converter.

        Args:
            cbm_dir: Directory for system files and processing
        """
        self._temp_files: Set[Path] = set()
        self.cbm_dir = Path(cbm_dir)
        self.temp_dir = self.cbm_dir / "temp_images"

        # Handle case where temp_dir exists but is not a directory
        if self.temp_dir.exists() and not self.temp_dir.is_dir():
            try:
                self.temp_dir.unlink()  # Remove if it's a file
            except Exception as e:
                logger.warning(f"Failed to remove existing temp_images file: {e}")

        # Create directory
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def convert_if_needed(self, image_path: Path) -> Optional[Path]:
        """Convert image to a supported format if necessary.

        Args:
            image_path: Path to the image file

        Returns:
            Path to the converted image, or None if conversion failed
        """
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        # Check if format needs conversion
        suffix = image_path.suffix.lower()
        if suffix == ".png":
            return self._convert_with_pillow(image_path)
        elif suffix in {".jpg", ".jpeg", ".gif"}:
            return image_path

        # Convert HEIC/HEIF to JPEG
        if suffix in {".heic", ".heif"}:
            return self._convert_heic(image_path)

        # Convert other formats using Pillow
        return self._convert_with_pillow(image_path)

    def _convert_heic(self, image_path: Path) -> Optional[Path]:
        """Convert HEIC/HEIF image to JPEG.

        Args:
            image_path: Path to the HEIC/HEIF image

        Returns:
            Path to the converted JPEG image, or None if conversion failed
        """
        output_path = self.temp_dir / f"{image_path.stem}.jpg"
        self._temp_files.add(output_path)

        # Try using sips on macOS first
        if platform.system() == "Darwin":
            try:
                result = subprocess.run(
                    ["sips", "-s", "format", "jpeg", str(image_path), "--out", str(output_path)],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    return output_path
                logger.warning(f"sips conversion failed for {image_path}, falling back to Pillow: {result.stderr}")
            except Exception as e:
                logger.warning(f"Unexpected error during sips conversion for {image_path}, falling back to Pillow: {e}")

        # Fall back to Pillow if sips fails or not on macOS
        try:
            return self._convert_with_pillow(image_path, output_path)
        except Exception as e:
            logger.error(f"Failed to convert HEIC image {image_path} with Pillow: {e}")
            return None

    def _convert_with_pillow(self, image_path: Path, output_path: Optional[Path] = None) -> Optional[Path]:
        """Convert image using Pillow.

        Args:
            image_path: Path to the image file
            output_path: Optional path for the output file

        Returns:
            Path to the converted image, or None if conversion failed
        """
        if output_path is None:
            output_path = self.temp_dir / f"{image_path.stem}.jpg"
            self._temp_files.add(output_path)

        try:
            with Image.open(image_path) as img:
                # Convert to RGB mode if necessary
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")

                # Save as JPEG with high quality
                img.save(output_path, "JPEG", quality=95)
                return output_path

        except Exception as e:
            logger.error(f"Failed to convert image {image_path} with Pillow: {e}")
            return None

    def cleanup(self) -> None:
        """Clean up temporary files."""
        # First, delete all temporary files
        for temp_file in list(self._temp_files):
            try:
                if temp_file.exists():
                    temp_file.unlink()
                    logger.debug(f"Deleted temporary file: {temp_file}")
                self._temp_files.remove(temp_file)
            except Exception as e:
                logger.warning(f"Failed to delete temporary file {temp_file}: {e}")

        # Then try to remove the temporary directory using shutil.rmtree
        try:
            if self.temp_dir.exists():
                # Remove all files in the directory first
                for file in self.temp_dir.iterdir():
                    try:
                        file.unlink()
                    except Exception as e:
                        logger.warning(f"Failed to delete file {file}: {e}")
                # Then try to remove the directory
                try:
                    self.temp_dir.rmdir()
                    logger.debug("Deleted temporary directory")
                except Exception as e:
                    logger.warning(f"Failed to delete temporary directory {self.temp_dir}: {e}")
        except Exception as e:
            logger.warning(f"Error cleaning up temporary directory {self.temp_dir}: {e}")

    def __del__(self) -> None:
        """Clean up on object deletion."""
        try:
            self.cleanup()
        except Exception as e:
            logger.warning(f"Error during cleanup in __del__: {e}")
