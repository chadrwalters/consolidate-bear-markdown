"""Image format conversion and optimization."""

import logging
from pathlib import Path
import platform
import subprocess
from typing import Optional

from PIL import Image

logger = logging.getLogger(__name__)


class ImageConverter:
    """Handles image format conversion and optimization."""

    def __init__(self, *, cbm_dir: str | Path) -> None:
        """Initialize with system directory.

        Args:
            cbm_dir: Directory for system files and processing
        """
        self.cbm_dir = Path(cbm_dir)
        self.temp_dir = self.cbm_dir / "temp"
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def convert_to_png(self, input_path: Path, output_path: Path) -> bool:
        """Convert any image format to PNG.

        Args:
            input_path: Path to input image
            output_path: Path to save PNG output

        Returns:
            True if conversion successful, False otherwise
        """
        try:
            # Handle SVG files separately using cairosvg
            if input_path.suffix.lower() == ".svg":
                return self.convert_svg(input_path, output_path)

            # Use PIL for other formats
            with Image.open(input_path) as img:
                # Convert to RGB if necessary
                if img.mode in ("RGBA", "LA") or (
                    img.mode == "P" and "transparency" in img.info
                ):
                    background = Image.new("RGB", img.size, (255, 255, 255))
                    if img.mode == "P":
                        img = img.convert("RGBA")
                    background.paste(img, mask=img.split()[-1])
                    img = background
                elif img.mode != "RGB":
                    img = img.convert("RGB")

                img.save(output_path, "PNG")
                return True

        except Exception as e:
            logger.error("Error converting image to PNG: %s", str(e))
            return False

    def convert_svg(self, input_path: Path, output_path: Path) -> bool:
        """Convert SVG to PNG using cairosvg.

        Args:
            input_path: Path to SVG file
            output_path: Path to save PNG output

        Returns:
            True if conversion successful, False otherwise
        """
        try:
            # Try using cairosvg if available
            try:
                import cairosvg

                cairosvg.svg2png(url=str(input_path), write_to=str(output_path))
                return True
            except ImportError:
                pass

            # Fallback to Inkscape if available
            try:
                result = subprocess.run(
                    [
                        "inkscape",
                        "--export-type=png",
                        "--export-filename",
                        str(output_path),
                        str(input_path),
                    ],
                    capture_output=True,
                    text=True,
                )
                return result.returncode == 0
            except FileNotFoundError:
                pass

            logger.error("No SVG conversion tools available (cairosvg or Inkscape)")
            return False

        except Exception as e:
            logger.error("Error converting SVG: %s", str(e))
            return False

    def convert_heic(
        self, image_path: Path, output_path: Optional[Path] = None
    ) -> Optional[Path]:
        """Convert HEIC to JPG.

        Args:
            image_path: Path to HEIC file
            output_path: Optional output path, defaults to same name with .jpg

        Returns:
            Path to converted file or None if conversion failed
        """
        if not image_path.exists():
            logger.error("HEIC file not found: %s", image_path)
            return None

        if output_path is None:
            output_path = self.temp_dir / f"{image_path.stem}.jpg"

        # Try sips on macOS first
        if platform.system() == "Darwin":
            try:
                result = subprocess.run(
                    [
                        "sips",
                        "-s",
                        "format",
                        "jpeg",
                        str(image_path),
                        "--out",
                        str(output_path),
                    ],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    return output_path
                logger.warning(
                    "sips conversion failed for %s: %s", image_path, result.stderr
                )
            except Exception as e:
                logger.warning(
                    "Unexpected error during sips conversion for %s: %s", image_path, e
                )

        # Fall back to Pillow
        return self._convert_with_pillow(image_path, output_path)

    def _convert_with_pillow(
        self, image_path: Path, output_path: Optional[Path] = None
    ) -> Optional[Path]:
        """Convert image using Pillow.

        Args:
            image_path: Path to image file
            output_path: Optional output path

        Returns:
            Path to converted file or None if conversion failed
        """
        try:
            if output_path is None:
                output_path = self.temp_dir / f"{image_path.stem}.png"

            with Image.open(image_path) as img:
                # Convert to RGB if needed
                if img.mode in ("RGBA", "LA"):
                    background = Image.new("RGB", img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[-1])
                    img = background
                elif img.mode not in ("RGB", "L"):
                    img = img.convert("RGB")

                # Save with high quality
                img.save(output_path, quality=95)
                return output_path

        except Exception as e:
            logger.error("Failed to convert image %s: %s", image_path, e)
            return None

    def cleanup(self) -> None:
        """Clean up temporary files."""
        try:
            if self.temp_dir.exists():
                try:
                    for file in self.temp_dir.iterdir():
                        try:
                            file.unlink()
                        except Exception as e:
                            logger.warning("Failed to delete file %s: %s", file, e)
                    self.temp_dir.rmdir()
                    logger.debug("Deleted temporary directory")
                except Exception as e:
                    logger.warning(
                        "Failed to delete temporary directory %s: %s", self.temp_dir, e
                    )
        except Exception as e:
            logger.warning(
                "Error cleaning up temporary directory %s: %s", self.temp_dir, e
            )

    def __del__(self) -> None:
        """Clean up on deletion."""
        self.cleanup()
