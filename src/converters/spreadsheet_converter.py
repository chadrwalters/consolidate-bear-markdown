"""Spreadsheet converter for Excel and CSV files."""

import logging
from pathlib import Path
from typing import Optional, Set, Union

import pandas as pd

from ..file_converter import ConversionResult

logger = logging.getLogger(__name__)


class SpreadsheetConverter:
    """Converts spreadsheet files to markdown tables."""

    SUPPORTED_EXTENSIONS: Set[str] = {".xlsx", ".xls", ".csv"}

    def __init__(self) -> None:
        """Initialize spreadsheet converter."""
        pass

    def can_handle(self, file_path: Path) -> bool:
        """Check if this converter can handle the given file."""
        return file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS

    def convert(self, file_path: Path) -> ConversionResult:
        """Convert a spreadsheet file to markdown."""
        try:
            logger.info("Reading spreadsheet file: %s", file_path.name)
            df = None

            if file_path.suffix.lower() == ".csv":
                # Try different encodings for CSV
                encodings = ["utf-8", "latin1", "cp1252"]
                last_error: Optional[Union[UnicodeDecodeError, Exception]] = None

                for encoding in encodings:
                    try:
                        df = pd.read_csv(file_path, encoding=encoding)
                        break
                    except UnicodeDecodeError as e:
                        last_error = e
                        continue
                    except Exception as e:
                        last_error = e
                        break

                if df is None:
                    if isinstance(last_error, UnicodeDecodeError):
                        raise last_error
                    raise Exception("Failed to read CSV with any encoding")
            else:
                # Excel files
                df = pd.read_excel(file_path)

            # Convert to markdown table
            md_table = df.to_markdown(index=False)
            formatted_content = (
                f"## Spreadsheet Content: {file_path.name}\n\n" f"{md_table}\n"
            )

            return {
                "success": True,
                "content": formatted_content,
                "type": "spreadsheet",
                "text_content": None,
                "text": None,
                "error": None,
                "error_type": None,
            }

        except Exception as e:
            logger.error("Failed to read spreadsheet %s: %s", file_path.name, str(e))
            return {
                "success": False,
                "content": None,
                "type": "spreadsheet",
                "text_content": None,
                "text": None,
                "error": f"Failed to read spreadsheet {file_path.name}: {str(e)}",
                "error_type": "spreadsheet_error",
            }
