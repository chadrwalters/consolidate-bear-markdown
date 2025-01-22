"""Document converter using pandoc and markitdown."""

import logging
from pathlib import Path
import subprocess
from typing import Set

from markitdown import MarkItDown  # type: ignore

from ..file_converter import ConversionResult

logger = logging.getLogger(__name__)


class DocumentConverter:
    """Converts document files to markdown using pandoc and markitdown."""

    SUPPORTED_EXTENSIONS: Set[str] = {".docx", ".doc", ".rtf", ".odt", ".pptx", ".ppt"}

    def __init__(
        self, pandoc_path: str = "pandoc", media_dir: Path = Path(".cbm/media")
    ):
        """Initialize document converter.

        Args:
            pandoc_path: Path to pandoc executable
            media_dir: Directory for extracted media files
        """
        self.pandoc_path = pandoc_path
        self.media_dir = media_dir
        self._verify_pandoc()
        self.markitdown = MarkItDown()

    def can_handle(self, file_path: Path) -> bool:
        """Check if this converter can handle the given file."""
        return file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS

    def convert(self, file_path: Path) -> ConversionResult:
        """Convert a document file to markdown."""
        try:
            # Determine input format based on file extension
            input_format = file_path.suffix.lstrip(".").lower()

            # Use markitdown for presentations
            if input_format in {"ppt", "pptx"}:
                try:
                    result = self.markitdown.convert(source=str(file_path))
                    return {
                        "success": True,
                        "content": result.text_content,
                        "type": "document",
                        "text_content": None,
                        "text": None,
                        "error": None,
                        "error_type": None,
                    }
                except Exception as e:
                    logger.error("Markitdown conversion failed: %s", str(e))
                    return {
                        "success": False,
                        "content": None,
                        "type": "document",
                        "text_content": None,
                        "text": None,
                        "error": f"Failed to convert presentation: {str(e)}",
                        "error_type": "markitdown_error",
                    }

            # Use pandoc for other document types
            if input_format in {"doc", "docx"}:
                input_format = "docx"

            # Build pandoc command
            cmd = [
                self.pandoc_path,
                "-f",
                input_format,
                "-t",
                "markdown",
                "--wrap=none",  # Disable text wrapping
                "--extract-media",
                str(self.media_dir),  # Extract embedded media
                str(file_path),
            ]

            # Run pandoc
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            return {
                "success": True,
                "content": result.stdout,
                "type": "document",
                "text_content": None,
                "text": None,
                "error": None,
                "error_type": None,
            }

        except subprocess.CalledProcessError as e:
            logger.error("Pandoc conversion failed: %s", e.stderr)
            return {
                "success": False,
                "content": None,
                "type": "document",
                "text_content": None,
                "text": None,
                "error": f"Failed to convert document: {e.stderr}",
                "error_type": "pandoc_error",
            }
        except Exception as e:
            logger.error("Document conversion failed: %s", str(e))
            return {
                "success": False,
                "content": None,
                "type": "document",
                "text_content": None,
                "text": None,
                "error": f"Failed to convert document: {str(e)}",
                "error_type": "conversion_error",
            }

    def _verify_pandoc(self) -> None:
        """Verify that pandoc is available and working."""
        try:
            subprocess.run(
                [self.pandoc_path, "--version"], capture_output=True, check=True
            )
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            raise RuntimeError(
                f"Pandoc not available or not working: {str(e)}\n"
                "Please install pandoc (https://pandoc.org/installing.html)"
            ) from e
