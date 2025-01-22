"""Binary file converter."""

import logging
import mimetypes
from pathlib import Path
from typing import Set

from ..file_converter import ConversionResult

logger = logging.getLogger(__name__)


class BinaryConverter:
    """Handles binary files that can't be directly converted."""

    # Extensions we know we can't convert but want to handle gracefully
    SUPPORTED_EXTENSIONS: Set[str] = {
        ".exe",
        ".dll",
        ".so",
        ".dylib",  # Executables and libraries
        ".zip",
        ".tar",
        ".gz",
        ".7z",  # Archives
        ".db",
        ".sqlite",
        ".sqlite3",  # Databases
        ".bin",
        ".dat",  # Generic binary
    }

    def __init__(self) -> None:
        """Initialize binary converter."""
        pass

    def can_handle(self, file_path: Path) -> bool:
        """Check if this converter can handle the given file.

        This converter acts as a fallback for binary files that
        other converters can't handle.
        """
        # First check our known binary extensions
        if file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS:
            return True

        # Then check if it's a binary file using mimetype
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if mime_type and not mime_type.startswith(("text/", "application/json")):
            return True

        return False

    def convert(self, file_path: Path) -> ConversionResult:
        """Handle a binary file by providing metadata."""
        try:
            # Get file info
            file_size = file_path.stat().st_size
            size_str = (
                f"{file_size/1024:.1f}KB"
                if file_size < 1024 * 1024
                else f"{file_size/(1024*1024):.1f}MB"
            )

            # Get mime type
            mime_type, encoding = mimetypes.guess_type(str(file_path))
            type_str = mime_type or "application/octet-stream"

            # Create info block
            content = (
                f"## Binary File: {file_path.name}\n\n"
                f"- **Type**: {type_str}\n"
                f"- **Size**: {size_str}\n"
                f"- **Encoding**: {encoding or 'binary'}\n\n"
                f"> This file is in binary format and cannot be displayed directly.\n"
                f"> Please access the original file to view its contents.\n"
            )

            return {
                "success": True,
                "content": content,
                "type": "binary",
                "text_content": None,
                "text": None,
                "error": None,
                "error_type": None,
            }

        except Exception as e:
            logger.error("Failed to process binary file %s: %s", file_path.name, str(e))
            return {
                "success": False,
                "content": None,
                "type": "binary",
                "text_content": None,
                "text": None,
                "error": f"Failed to process binary file {file_path.name}: {str(e)}",
                "error_type": "binary_error",
            }
