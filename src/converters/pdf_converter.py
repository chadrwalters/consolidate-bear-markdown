"""PDF converter using PyMuPDF."""

import logging
from pathlib import Path
from typing import List, Set

import fitz  # type: ignore

from ..file_converter import ConversionResult

logger = logging.getLogger(__name__)


class PDFConverter:
    """Converts PDF files to markdown."""

    SUPPORTED_EXTENSIONS: Set[str] = {".pdf"}

    def __init__(self) -> None:
        """Initialize PDF converter."""
        pass

    def can_handle(self, file_path: Path) -> bool:
        """Check if this converter can handle the given file."""
        return file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS

    def convert(self, file_path: Path) -> ConversionResult:
        """Convert a PDF file to markdown."""
        try:
            logger.info("Converting PDF: %s", file_path.name)
            text_content: List[str] = []

            # Open the PDF
            doc = fitz.open(str(file_path))

            # Extract text from each page
            for page_num in range(doc.page_count):
                page = doc[page_num]
                text = page.get_text()  # type: ignore
                if text.strip():  # Only add non-empty pages
                    text_content.append(f"### Page {page_num + 1}\n\n{text}")

            # Close the document
            doc.close()

            # Format the content
            if text_content:
                content = "\n\n".join(text_content)
                return {
                    "success": True,
                    "content": content,
                    "type": "pdf",
                    "text_content": content,
                    "text": None,
                    "error": None,
                    "error_type": None,
                }
            else:
                return {
                    "success": False,
                    "content": None,
                    "type": "pdf",
                    "text_content": None,
                    "text": None,
                    "error": "No text content found in PDF",
                    "error_type": "empty_pdf",
                }

        except Exception as e:
            logger.error("Failed to convert PDF %s: %s", file_path.name, str(e))
            return {
                "success": False,
                "content": None,
                "type": "pdf",
                "text_content": None,
                "text": None,
                "error": f"Failed to convert PDF {file_path.name}: {str(e)}",
                "error_type": "pdf_error",
            }
