"""Factory for creating file converters."""

import logging
from pathlib import Path
from typing import List, Optional, Union, cast

from openai import OpenAI

from .converters.binary_converter import BinaryConverter
from .converters.document_converter import DocumentConverter
from .converters.image_converter import ImageConverter
from .converters.pdf_converter import PDFConverter
from .converters.spreadsheet_converter import SpreadsheetConverter
from .converters.text_converter import TextConverter
from .file_converter import ConversionResult, FileConverter

# We'll add other converters as we create them:
# from .converters.image_converter import ImageConverter
# from .converters.spreadsheet_converter import SpreadsheetConverter
# etc.

logger = logging.getLogger(__name__)

# Type alias for all converter types
ConverterType = Union[
    DocumentConverter,
    ImageConverter,
    SpreadsheetConverter,
    TextConverter,
    PDFConverter,
    BinaryConverter,
]


class ConverterFactory:
    """Factory for creating and managing file converters."""

    def __init__(self, *, cbm_dir: Path, openai_client: Optional[OpenAI] = None):
        """Initialize the converter factory.

        Args:
            cbm_dir: Directory for system files and processing
            openai_client: Optional OpenAI client for AI-powered conversions

        Raises:
            ValueError: If openai_client is None but required by a converter
        """
        self.cbm_dir = cbm_dir
        self.media_dir = cbm_dir / "media"
        self.media_dir.mkdir(parents=True, exist_ok=True)

        # Initialize converters in order of preference
        converters: List[ConverterType] = [
            DocumentConverter(media_dir=self.media_dir),
            PDFConverter(),
            SpreadsheetConverter(),
            TextConverter(),
        ]

        # Add image converter only if we have an OpenAI client
        if openai_client is not None:
            converters.append(
                ImageConverter(openai_client=openai_client, cbm_dir=cbm_dir)
            )
        else:
            logger.warning(
                "No OpenAI client provided - image analysis will be unavailable"
            )

        # Add binary converter last as a fallback
        converters.append(BinaryConverter())

        self.converters = cast(List[FileConverter], converters)

    def get_converter(self, file_path: Path) -> Optional[FileConverter]:
        """Get the appropriate converter for a file.

        Args:
            file_path: Path to the file

        Returns:
            Converter that can handle the file, or None if no converter found
        """
        for converter in self.converters:
            if converter.can_handle(file_path):
                return converter
        return None

    def convert_file(self, file_path: Path) -> ConversionResult:
        """Convert a file using the appropriate converter.

        Args:
            file_path: Path to the file to convert

        Returns:
            Conversion result
        """
        converter = self.get_converter(file_path)
        if converter is None:
            return {
                "success": False,
                "content": None,
                "type": "unknown",
                "text_content": None,
                "text": None,
                "error": f"No converter found for file: {file_path}",
                "error_type": "unsupported_type",
            }

        try:
            return converter.convert(file_path)
        except Exception as e:
            logger.error("Error converting file %s: %s", file_path, str(e))
            return {
                "success": False,
                "content": None,
                "type": "unknown",
                "text_content": None,
                "text": None,
                "error": f"Error converting file: {str(e)}",
                "error_type": "conversion_error",
            }
