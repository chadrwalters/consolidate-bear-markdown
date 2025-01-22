"""Image converter using GPT-4o vision model."""

import base64
import logging
from pathlib import Path
from typing import Optional, Set

from openai import OpenAI
from PIL import Image

try:
    import pillow_heif  # type: ignore

    HEIF_SUPPORT = True
except ImportError:
    HEIF_SUPPORT = False

from ..file_converter import ConversionResult
from ..image_cache import ImageCache
from ..logging_utils import log_timing, log_block_timing

logger = logging.getLogger(__name__)


class ImageConverter:
    """Converts image files to markdown with AI-powered analysis."""

    SUPPORTED_EXTENSIONS: Set[str] = {
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".webp",
        ".heic",
        ".heif",
        ".svg",
    }

    def __init__(self, *, openai_client: Optional[OpenAI], cbm_dir: Path):
        """Initialize image converter.

        Args:
            openai_client: OpenAI client for image analysis
            cbm_dir: Directory for system files and caching
        """
        self.client = openai_client
        self.cbm_dir = cbm_dir
        self.cache = ImageCache(cbm_dir=cbm_dir)
        self.temp_dir = cbm_dir / "temp_images"
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        # Set OpenAI logger to WARNING to avoid base64 data in logs
        logging.getLogger("openai").setLevel(logging.WARNING)
        logging.getLogger("openai._base_client").setLevel(logging.WARNING)

        if not HEIF_SUPPORT:
            logger.warning(
                "pillow-heif not installed. HEIC/HEIF support will be limited."
            )

    def can_handle(self, file_path: Path) -> bool:
        """Check if this converter can handle the given file.

        Args:
            file_path: Path to the file

        Returns:
            True if this converter can handle the file
        """
        # Only handle images if we have an OpenAI client
        if not self.client:
            return False
        return file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS

    @log_timing
    def convert(self, file_path: Path) -> ConversionResult:
        """Convert an image file to markdown with analysis."""
        if not file_path.exists():
            return {
                "success": False,
                "content": None,
                "type": "image",
                "text_content": None,
                "text": None,
                "error": f"File not found: {file_path}",
                "error_type": "file_not_found",
            }

        if not self.client:
            return {
                "success": False,
                "content": None,
                "type": "image",
                "text_content": None,
                "text": None,
                "error": "OpenAI client not available",
                "error_type": "client_not_available",
            }

        try:
            # Check cache first
            if self.cache.is_processed(file_path):
                with log_block_timing(f"Cache lookup for {file_path.name}"):
                    cached_path = self.cache.get_cached_path(file_path)
                    if cached_path:
                        cached_analysis = cached_path.read_text()
                        logger.info(f"Using cached analysis for {file_path.name}")
                        return {
                            "success": True,
                            "content": self._format_analysis(cached_analysis, file_path),
                            "type": "image",
                            "text_content": None,
                            "text": None,
                            "error": None,
                            "error_type": None,
                        }

            # Process image
            with log_block_timing(f"Image processing for {file_path.name}"):
                # Convert to supported format if needed
                processed_path = self._convert_to_supported_format(file_path)
                if not processed_path:
                    return {
                        "success": False,
                        "content": None,
                        "type": "image",
                        "text_content": None,
                        "text": None,
                        "error": f"Failed to convert {file_path.name} to supported format",
                        "error_type": "conversion_error",
                    }

                # Analyze with GPT-4o
                analysis = self._analyze_with_gpt4o(processed_path)
                if not analysis:
                    return {
                        "success": False,
                        "content": None,
                        "type": "image",
                        "text_content": None,
                        "text": None,
                        "error": f"Failed to analyze {file_path.name}",
                        "error_type": "analysis_error",
                    }

                # Cache the result
                with log_block_timing(f"Cache storage for {file_path.name}"):
                    self.cache.cache_analysis(file_path, analysis)

                return {
                    "success": True,
                    "content": self._format_analysis(analysis, file_path),
                    "type": "image",
                    "text_content": None,
                    "text": None,
                    "error": None,
                    "error_type": None,
                }

        except Exception as e:
            logger.error("Failed to process image %s: %s", file_path.name, str(e))
            return {
                "success": False,
                "content": None,
                "type": "image",
                "text_content": None,
                "text": None,
                "error": str(e),
                "error_type": "processing_error",
            }

    def _format_analysis(self, analysis: str, file_path: Path) -> str:
        """Format image analysis with metadata."""
        try:
            # Get image dimensions
            dimensions = ""
            try:
                with Image.open(file_path) as img:
                    dimensions = f"{img.width}x{img.height}, "
            except Exception:
                pass

            # Get file metadata
            file_size = file_path.stat().st_size
            size_str = f"{file_size/1024:.1f}KB"

            return (
                f"## Image Analysis: {file_path.name}\n\n"
                f"**Details**: {dimensions}{size_str}\n\n"
                f"{analysis}\n"
            )
        except Exception as e:
            logger.error("Error formatting analysis: %s", str(e))
            return analysis

    def _convert_to_png(self, input_path: Path, output_path: Path) -> bool:
        """Convert image to PNG format."""
        try:
            ext = input_path.suffix.lower()

            # Handle HEIC/HEIF files
            if ext in {".heic", ".heif"}:
                if not HEIF_SUPPORT:
                    logger.error("pillow-heif required for HEIC/HEIF support")
                    return False

                try:
                    heif_file = pillow_heif.read_heif(str(input_path))
                    if not heif_file.data:
                        logger.error("No data in HEIC/HEIF file")
                        return False
                    image = Image.frombytes(
                        heif_file.mode,
                        heif_file.size,
                        heif_file.data,
                        "raw",
                    )
                    image.save(output_path, "PNG")
                    return True
                except Exception as e:
                    logger.error(f"HEIC/HEIF conversion failed: {e}")
                    return False

            if ext == ".svg":
                # Use nocairosvg for SVG conversion
                try:
                    from nocairosvg import svg2png

                    svg2png(url=str(input_path), write_to=str(output_path), dpi=300)
                    return True
                except Exception as e:
                    logger.error("SVG conversion failed: %s", str(e))
                    return False

            # Use PIL for other formats
            with Image.open(input_path) as img:
                # Convert to RGB if needed
                if img.mode in ("RGBA", "LA") or (
                    img.mode == "P" and "transparency" in img.info
                ):
                    img = img.convert("RGBA")
                    background = Image.new("RGBA", img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[3])
                    img = background.convert("RGB")
                elif img.mode != "RGB":
                    img = img.convert("RGB")

                img.save(output_path, "PNG")
                return True

        except Exception as e:
            logger.error("Image conversion failed: %s", str(e))
            return False

    def _convert_to_supported_format(self, file_path: Path) -> Optional[Path]:
        """Convert image to a supported format if needed.

        Args:
            file_path: Path to the image file

        Returns:
            Path to the converted file, or None if conversion failed
        """
        # If already in supported format, return as is
        if file_path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
            return file_path

        # Convert HEIC/HEIF to PNG
        if file_path.suffix.lower() in {".heic", ".heif"}:
            working_path = self.temp_dir / f"{file_path.stem}.png"
            if not self._convert_to_png(file_path, working_path):
                return None
            return working_path

        # Convert SVG to PNG
        if file_path.suffix.lower() == ".svg":
            working_path = self.temp_dir / f"{file_path.stem}.png"
            if not self._convert_to_png(file_path, working_path):
                return None
            return working_path

        return None

    def _analyze_with_gpt4o(self, image_path: Path) -> Optional[str]:
        """Analyze image using GPT-4o vision model.

        Args:
            image_path: Path to the image file

        Returns:
            Analysis text, or None if analysis failed
        """
        if not self.client:
            logger.error("OpenAI client not available")
            return None

        try:
            with open(image_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode()

            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Describe this image in detail.",
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_data}",
                                    "detail": "high",
                                },
                            },
                        ],
                    }
                ],
            )

            if response and response.choices and response.choices[0].message:
                return response.choices[0].message.content
            return None

        except Exception as e:
            logger.error("Failed to analyze image with GPT-4o: %s", str(e))
            return None

    def cleanup(self) -> None:
        """Clean up temporary files."""
        self.cache.cleanup()
        try:
            if self.temp_dir.exists():
                for file in self.temp_dir.iterdir():
                    try:
                        file.unlink()
                    except Exception as e:
                        logger.debug(f"Error deleting file {file}: {e}")
                self.temp_dir.rmdir()
        except Exception as e:
            logger.debug(f"Error cleaning up temporary directory: {e}")

    def __del__(self) -> None:
        """Clean up on deletion."""
        self.cleanup()
