"""MarkItDown class for converting various file types to markdown."""

import logging
from pathlib import Path
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)


class MarkItDown:
    """Class for converting various file types to markdown."""

    def __init__(self, pandoc_path: Optional[str] = None):
        """Initialize MarkItDown.

        Args:
            pandoc_path: Optional path to pandoc executable. If not provided,
                        will use pandoc from system PATH.
        """
        self.pandoc_path = pandoc_path or "pandoc"
        self._verify_pandoc()

    def _verify_pandoc(self) -> None:
        """Verify that pandoc is available and working.

        Raises:
            RuntimeError: If pandoc is not available or not working.
        """
        try:
            subprocess.run(
                [self.pandoc_path, "--version"], capture_output=True, check=True
            )
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            raise RuntimeError(
                f"Pandoc not available or not working: {str(e)}\n"
                "Please install pandoc (https://pandoc.org/installing.html)"
            ) from e

    def convert_document(self, file_path: str) -> str:
        """Convert a document file to markdown.

        Args:
            file_path: Path to the document file

        Returns:
            Markdown string representation of the document

        Raises:
            RuntimeError: If conversion fails
        """
        try:
            # Determine input format based on file extension
            input_format = Path(file_path).suffix.lstrip(".")
            if input_format == "docx":
                input_format = "docx"
            elif input_format == "pptx":
                input_format = "pptx"
            else:
                input_format = "docx"  # Default to docx for unknown types

            # Use pandoc to convert document to markdown
            result = subprocess.run(
                [
                    self.pandoc_path,
                    "-f",
                    input_format,
                    "-t",
                    "markdown",
                    "--wrap=none",  # Disable text wrapping
                    "--extract-media=.cbm/media",  # Extract embedded media
                    file_path,
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout

        except subprocess.CalledProcessError as e:
            logger.error("Pandoc conversion failed: %s", e.stderr)
            raise RuntimeError(f"Failed to convert document: {e.stderr}") from e
        except Exception as e:
            logger.error("Document conversion failed: %s", str(e))
            raise RuntimeError(f"Failed to convert document: {str(e)}") from e
