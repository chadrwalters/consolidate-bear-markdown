"""Text and HTML converter."""

import logging
from pathlib import Path
from typing import Set

from bs4 import BeautifulSoup

from ..file_converter import ConversionResult

logger = logging.getLogger(__name__)


class TextConverter:
    """Converts text and HTML files to markdown."""

    SUPPORTED_EXTENSIONS: Set[str] = {".txt", ".html", ".json", ".log", ".md"}

    def __init__(self) -> None:
        """Initialize text converter."""
        pass

    def can_handle(self, file_path: Path) -> bool:
        """Check if this converter can handle the given file."""
        return file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS

    def convert(self, file_path: Path) -> ConversionResult:
        """Convert a text file to markdown."""
        try:
            # Try different encodings
            encodings = ["utf-8", "latin1", "cp1252"]
            content = None
            last_error = None

            for encoding in encodings:
                try:
                    with open(file_path, "r", encoding=encoding) as f:
                        content = f.read()
                        break
                except UnicodeDecodeError as e:
                    last_error = e
                    continue
                except UnicodeError:  # More specific than Exception
                    # Create a generic UnicodeDecodeError since we don't have the specific details
                    last_error = UnicodeDecodeError('utf-8', b'', 0, 1, 'Unknown encoding error')
                    break

            if content is None:
                raise last_error or Exception("Failed to read file with any encoding")

            # Process based on file type
            file_type = file_path.suffix.lower()
            if file_type == ".html":
                content = self._process_html(content)
            elif file_type == ".json":
                content = self._process_json(content)
            else:
                content = self._process_text(content)

            return {
                "success": True,
                "content": content,
                "type": file_type.lstrip("."),
                "text_content": None,
                "text": None,
                "error": None,
                "error_type": None,
            }

        except Exception as e:
            logger.error("Failed to read file %s: %s", file_path.name, str(e))
            return {
                "success": False,
                "content": None,
                "type": "text",
                "text_content": None,
                "text": None,
                "error": f"Failed to read file {file_path.name}: {str(e)}",
                "error_type": "text_error",
            }

    def _process_html(self, content: str) -> str:
        """Process HTML content."""
        try:
            # Parse HTML and extract text
            soup = BeautifulSoup(content, "html.parser")
            text_content = soup.get_text(separator="\n\n")
            return f"```html\n{content}\n```\n\n### Extracted Text:\n\n{text_content}"
        except Exception as e:
            logger.error("HTML processing failed: %s", str(e))
            return f"```html\n{content}\n```"

    def _process_json(self, content: str) -> str:
        """Process JSON content."""
        try:
            import json

            # Pretty print JSON
            parsed = json.loads(content)
            formatted = json.dumps(parsed, indent=2)
            return f"```json\n{formatted}\n```"
        except Exception as e:
            logger.error("JSON processing failed: %s", str(e))
            return f"```json\n{content}\n```"

    def _process_text(self, content: str) -> str:
        """Process plain text content."""
        return f"```\n{content}\n```"
