"""File converter interface and result types."""

from pathlib import Path
from typing import Optional, Protocol, TypedDict


class ConversionResult(TypedDict, total=False):
    """Type hints for conversion result."""

    success: bool
    type: str
    content: Optional[str]
    text_content: Optional[str]
    text: Optional[str]
    error: Optional[str]
    error_type: Optional[str]


class FileConverter(Protocol):
    """Interface for file converters."""

    def can_handle(self, file_path: Path) -> bool:
        """Check if this converter can handle the given file.

        Args:
            file_path: Path to the file

        Returns:
            True if this converter can handle the file
        """
        ...

    def convert(self, file_path: Path) -> ConversionResult:
        """Convert a file to markdown format.

        Args:
            file_path: Path to the file to convert

        Returns:
            Conversion result with standardized format
        """
        ...

    def cleanup(self) -> None:
        """Clean up any resources used by the converter.

        This method is optional. Converters that need cleanup should implement it.
        """
        ...
