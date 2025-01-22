"""MarkItDown wrapper with standardized output formats."""

import base64
import json
import logging
import os
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, TypedDict, Union

from bs4 import BeautifulSoup
import fitz  # type: ignore
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam
import pandas as pd
from PIL import Image

from markitdown import MarkItDown  # type: ignore

from .image_cache import ImageCache
from .image_converter import ImageConverter

# Configure OpenAI loggers to not show debug messages
logging.getLogger("openai").setLevel(logging.INFO)
logging.getLogger("openai._base_client").setLevel(logging.INFO)
logging.getLogger("pdfminer.cmapdb").setLevel(logging.INFO)

logger = logging.getLogger(__name__)


class DocumentConverterResult(TypedDict, total=False):
    """Type hints for MarkItDown conversion result."""

    success: bool
    type: str
    content: Optional[str]
    text_content: Optional[str]
    text: Optional[str]
    error: Optional[str]
    error_type: Optional[str]


def create_error_result(error_msg: str, error_type: str = "unknown") -> Dict[str, Any]:
    """Create a standardized error result.

    Args:
        error_msg: Error message
        error_type: Type of error

    Returns:
        Error result dictionary
    """
    return {
        "success": False,
        "content": None,
        "error": error_msg,
        "error_type": error_type,
        "type": "unknown",
        "text_content": None,
        "text": None,
    }


def create_success_result(
    content: str,
    type_str: str,
    text_content: Optional[str] = None,
    text: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a standardized success result.

    Args:
        content: Converted content
        type_str: Type of content
        text_content: Optional text content
        text: Optional raw text

    Returns:
        Success result dictionary
    """
    return {
        "success": True,
        "content": content,
        "type": type_str,
        "text_content": text_content,
        "text": text,
        "error": None,
        "error_type": None,
    }


class MarkItDownWrapper:
    """Wrapper for MarkItDown with standardized output formats."""

    def __init__(self, client: OpenAI, *, cbm_dir: str | Path) -> None:
        """Initialize wrapper with OpenAI client.

        Args:
            client: OpenAI client instance
            cbm_dir: Directory for system files and processing
        """
        self.client = client
        self.max_retries = 3
        self.retry_delay = 1
        self.cbm_dir = Path(cbm_dir)
        self.image_cache = ImageCache(cbm_dir=self.cbm_dir)
        self.image_converter = ImageConverter(cbm_dir=self.cbm_dir)
        self.markitdown = MarkItDown(llm_client=client, llm_model="gpt-4o")
        logger.debug("MarkItDownWrapper initialized with cbm_dir: %s", self.cbm_dir)
        self.temp_dir = self.cbm_dir / "temp"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.temp_images = self.temp_dir / "temp_images"
        self.temp_images.mkdir(parents=True, exist_ok=True)

    def _handle_pdf_file(self, file_path: Path) -> Dict[str, Any]:
        """Handle PDF file conversion using PyMuPDF."""
        try:
            # Open the PDF
            doc = fitz.open(str(file_path))
            text_content = []

            # Extract text from each page
            for page in doc:
                text_content.append(page.get_text())  # type: ignore

            # Close the document
            doc.close()

            return {
                "text_content": "\n\n".join(text_content),
                "success": True,
                "type": "pdf",
                "content": None,
                "text": None,
                "error": None,
                "error_type": None,
            }
        except Exception as e:
            logger.error("Error converting PDF: %s", str(e))
            return {
                "text_content": None,
                "success": False,
                "error": f"Error converting PDF: {str(e)}",
                "type": "pdf",
                "content": None,
                "text": None,
                "error_type": "pdf_conversion_error",
            }

    def convert_file(self, file_path: Path) -> Dict[str, Any]:
        """Convert a file to markdown format.

        Args:
            file_path: Path to the file to convert

        Returns:
            Conversion result with standardized format
        """
        file_type = self._get_file_type(file_path)

        if file_type == "pdf":
            return self._handle_pdf_file(file_path)
        elif file_type == "image":
            return self._handle_image_file(file_path)
        elif file_type == "document":
            return self._handle_document_file(file_path)
        elif file_type == "spreadsheet":
            result = self._handle_spreadsheet_file(file_path)
            return {
                **result,
                "text_content": None,
                "text": None,
                "error_type": result.get("error_type", None),
            }
        elif file_type == "html":
            result = self._handle_html_file(file_path)
            return {
                **result,
                "text_content": None,
                "text": None,
                "error_type": result.get("error_type", None),
            }
        elif file_type == "json":
            result = self._handle_json_file(file_path)
            return {
                **result,
                "text_content": None,
                "text": None,
                "error_type": result.get("error_type", None),
            }
        elif file_type == "text":
            result = self._handle_text_file(file_path)
            return {
                **result,
                "text_content": None,
                "text": None,
                "error_type": result.get("error_type", None),
            }
        else:
            return create_error_result(
                f"Unsupported file type: {file_type}", "unsupported_type"
            )

    def _format_cannot_parse(
        self,
        filename: str,
        error_type: str = "parse_error",
        error_msg: str = "Cannot be parsed.",
    ) -> Dict[str, Any]:
        """Format message for files that cannot be parsed."""
        file_path = Path(filename)
        file_info = file_path.stat() if file_path.exists() else None

        # Format file size
        size_str = f"{file_info.st_size / 1024:.2f} KB" if file_info else "Unknown"

        # Format last modified time
        modified_str = time.ctime(file_info.st_mtime) if file_info else "Unknown"

        content = (
            f"## Unsupported Attachment: {filename}\n\n"
            f"### File Details\n"
            f"- **File Type**: {file_path.suffix.lstrip('.').upper()}\n"
            f"- **Size**: {size_str}\n"
            f"- **Last Modified**: {modified_str}\n\n"
            f"### Error Information\n"
            f"- **Error Type**: {error_type}\n"
            f"- **Error Message**: {error_msg}\n\n"
            "> This file type cannot be processed directly. "
            "Please access the original file for content.\n"
        )

        return {
            "success": False,
            "content": content,
            "type": "file",
            "error": error_msg,
            "error_type": error_type,
            "text_content": None,
            "text": None,
        }

    def _handle_image_file(self, file_path: Path) -> Dict[str, Any]:
        """Handle image file conversion."""
        # Check if file exists
        if not file_path.exists():
            return {
                "success": False,
                "content": None,
                "error": f"File not found: {file_path.name}",
                "type": "image",
                "text_content": None,
                "text": None,
                "error_type": "file_not_found",
            }

        try:
            # Check cache
            if self.image_cache.is_processed(file_path):
                cached_path = self.image_cache.get_cached_path(file_path)
                if cached_path:
                    logger.info(f"Using cached analysis for {file_path.name}")
                    return {
                        "success": True,
                        "content": self._format_image_analysis(
                            cached_path.read_text(), file_path.name
                        ),
                        "type": "image",
                        "text_content": None,
                        "text": None,
                        "error": None,
                        "error_type": None,
                    }

            # Handle HEIC files first
            if file_path.suffix.lower() in {".heic", ".heif"}:
                converted_path = self.image_converter.convert_heic(file_path)
                if not converted_path:
                    return {
                        "success": False,
                        "content": None,
                        "error": f"Failed to convert HEIC file: {file_path.name}",
                        "type": "image",
                        "text_content": None,
                        "text": None,
                        "error_type": "heic_conversion_error",
                    }
                file_path = converted_path

            # Convert image to PNG if not in supported format
            supported_formats = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
            if file_path.suffix.lower() not in supported_formats:
                png_path = self.temp_images / f"{file_path.stem}.png"
                if not self.image_converter.convert_to_png(file_path, png_path):
                    return {
                        "success": False,
                        "content": None,
                        "error": f"Failed to convert {file_path.suffix} to PNG",
                        "type": "image",
                        "text_content": None,
                        "text": None,
                        "error_type": "image_conversion_error",
                    }
                file_path = png_path

            # Process the image
            with open(file_path, "rb") as f:
                image_data = f.read()
                base64_image = base64.b64encode(image_data).decode()

            # Analyze with GPT-4o
            try:
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
                                        "url": f"data:image/jpeg;base64,{base64_image}",
                                        "detail": "high",
                                    },
                                },
                            ],
                        }
                    ],
                )
                analysis = response.choices[0].message.content
            except Exception as e:
                logger.error("Error analyzing image: %s", str(e))
                return {
                    "success": False,
                    "content": None,
                    "error": f"Error analyzing image: {str(e)}",
                    "type": "image",
                    "text_content": None,
                    "text": None,
                    "error_type": "analysis_error",
                }

            # Cache successful analysis
            if analysis is not None:
                self.image_cache.cache_analysis(file_path, analysis)

            return {
                "success": True,
                "content": self._format_image_analysis(analysis, file_path.name),
                "type": "image",
                "text_content": None,
                "text": None,
                "error": None,
                "error_type": None,
            }

        except Exception as e:
            logger.error("Error processing image: %s", str(e))
            return {
                "success": False,
                "content": None,
                "error": f"Error processing image: {str(e)}",
                "type": "image",
                "text_content": None,
                "text": None,
                "error_type": "processing_error",
            }

    def process_markdown(self, content: str, processed_paths: Dict[str, Path]) -> str:
        """Process markdown content with processed attachment paths.

        Args:
            content: The markdown content to process
            processed_paths: Dictionary mapping original paths to processed paths

        Returns:
            Processed markdown content with updated references
        """
        try:
            # Replace attachment references with processed paths
            processed_content = content
            for original_path, processed_path in processed_paths.items():
                processed_content = processed_content.replace(
                    f"]({original_path})", f"]({processed_path})"
                )
            return processed_content

        except Exception as e:
            logger.error(f"Error processing markdown content: {e}")
            return content

    def process_image(self, image_path: Path) -> Dict[str, Any]:
        """Process an image using GPT-4o vision model.

        Args:
            image_path: Path to the image file

        Returns:
            Dictionary containing the processing results
        """
        if not image_path.exists():
            logger.error(f"Image file not found: {image_path}")
            return {
                "success": False,
                "content": None,
                "error": f"Image file not found: {image_path}",
            }

        try:
            # Read image file
            with open(image_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode("utf-8")

            # Process with retries
            for attempt in range(self.max_retries):
                try:
                    messages: List[ChatCompletionMessageParam] = [
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
                    ]

                    # Avoid logging base64 data
                    logger.debug("Sending request to OpenAI API with image data")
                    response = self.client.chat.completions.create(
                        model="gpt-4o", messages=messages
                    )

                    # Extract and format the response
                    if response and response.choices and response.choices[0].message:
                        description = response.choices[0].message.content or ""
                        return {"success": True, "text": description, "error": None}
                    else:
                        raise ValueError("Invalid response from OpenAI API")

                except Exception as e:
                    if attempt == self.max_retries - 1:
                        raise
                    logger.warning(f"Retry {attempt + 1} failed: {e}")
                    time.sleep(self.retry_delay)

            return {
                "success": False,
                "content": None,
                "error": f"Failed to process image after {self.max_retries} attempts",
            }

        except Exception as e:
            logger.error(f"Failed to process image {image_path}: {e}")
            return {"success": False, "content": None, "error": str(e)}

    def _get_file_emoji(self, file_type: str) -> str:
        """Get emoji for file type.

        Args:
            file_type: Type of file (e.g., 'document', 'spreadsheet', 'image')

        Returns:
            Emoji string for the file type
        """
        emoji_map = {
            "document": "📄",
            "spreadsheet": "📊",
            "image": "🖼️",
            "code": "",
            "pdf": "📑",
            "text": "📝",
            "html": "🌐",
            "json": "📋",
        }
        return emoji_map.get(file_type, "📄")

    def _get_file_type(self, file_path: Path) -> str:
        """Determine file type from extension.

        Args:
            file_path: Path to the file

        Returns:
            File type string
        """
        ext = file_path.suffix.lower()
        if ext in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".heif", ".svg"}:
            return "image"
        elif ext in {".xlsx", ".csv"}:
            return "spreadsheet"
        elif ext in {".docx", ".doc", ".rtf"}:
            return "document"
        elif ext == ".pdf":
            return "pdf"
        elif ext == ".html":
            return "html"
        elif ext == ".json":
            return "json"
        elif ext == ".txt":
            return "text"
        elif ext in {".py", ".js", ".java", ".cpp"}:
            return "code"
        return "document"

    def _format_file_content(self, content: str, filename: str) -> str:
        """Format file content with improved readability.

        Args:
            content: Raw content to format
            filename: Name of the file

        Returns:
            Formatted content string
        """
        file_path = Path(filename)
        file_type = self._get_file_type(file_path)
        emoji = self._get_file_emoji(file_type)

        # Get file metadata
        file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
        size_str = f"{file_size/1024:.1f}KB" if file_size > 0 else "unknown size"
        mod_time = (
            time.strftime("%b %d", time.localtime(os.path.getmtime(file_path)))
            if os.path.exists(file_path)
            else ""
        )

        # Format the content
        formatted = f"""<!-- BEGIN EMBEDDED CONTENT -->
<details class="embedded-content">
<summary>{emoji} {filename} ({size_str}, modified {mod_time})</summary>

{content}

</details>
<!-- END EMBEDDED CONTENT -->"""
        return formatted

    def _format_image_analysis(self, analysis: Optional[str], filename: str) -> str:
        """Format image analysis with improved readability.

        Args:
            analysis: Image analysis text (can be None)
            filename: Name of the image file

        Returns:
            Formatted analysis string
        """
        file_path = Path(filename)

        # Get image dimensions if possible
        dimensions = self._get_dimensions(file_path)

        # Get file metadata
        file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
        size_str = f"{file_size/1024:.1f}KB" if file_size > 0 else "unknown size"
        mod_time = (
            time.strftime("%b %d", time.localtime(os.path.getmtime(file_path)))
            if os.path.exists(file_path)
            else ""
        )

        formatted = f"""<!-- BEGIN EMBEDDED CONTENT -->
<details class="embedded-content">
<summary>🖼️ {filename} ({dimensions}{size_str}, modified {mod_time})</summary>

{analysis or "No analysis available"}

</details>
<!-- END EMBEDDED CONTENT -->"""
        return formatted

    def _get_dimensions(self, file_path: Path) -> str:
        """Get image dimensions if possible."""
        try:
            with Image.open(file_path) as img:
                return f"{img.width}x{img.height}, "
        except Exception:  # Catch specific exceptions instead of bare except
            return ""

    def _format_error(self, error_type: str, error_msg: str) -> Dict[str, Any]:
        """Format error message."""
        return {
            "success": False,
            "content": None,
            "error": error_msg,
            "error_type": error_type,
            "type": "error",
            "text_content": None,
            "text": None,
        }

    def cleanup(self) -> None:
        """Clean up resources."""
        self.image_cache.cleanup()
        self.image_converter.cleanup()
        try:
            if self.temp_images.exists():
                for file in self.temp_images.iterdir():
                    try:
                        file.unlink()
                    except Exception as e:
                        logger.debug(f"Error deleting file {file}: {e}")
                self.temp_images.rmdir()
            if self.temp_dir.exists():
                self.temp_dir.rmdir()
        except Exception as e:
            logger.debug(f"Error cleaning up temporary directory: {e}")

    def __del__(self) -> None:
        """Clean up on deletion."""
        self.cleanup()

    def _handle_spreadsheet_file(self, file_path: Path) -> Dict[str, Any]:
        """Handle spreadsheet file conversion.

        Args:
            file_path: Path to the spreadsheet file

        Returns:
            Dictionary containing the conversion results
        """
        try:
            logger.info("Reading spreadsheet file: %s", file_path.name)
            # Try different encodings
            encodings = ["utf-8", "latin1", "cp1252"]
            df = None
            last_error: Optional[Union[UnicodeDecodeError, Exception]] = None

            if file_path.suffix.lower() == ".csv":
                for encoding in encodings:
                    try:
                        df = pd.read_csv(file_path, encoding=encoding)
                        break
                    except UnicodeDecodeError as e:
                        last_error = e
                        continue
                    except UnicodeError as e:  # More specific than Exception
                        last_error = e
                        break

                if df is None:
                    error_msg = "Failed to read CSV with any encoding"
                    raise last_error or Exception(error_msg)
            else:  # Excel files
                df = pd.read_excel(file_path)

            # Convert to markdown table
            md_table = df.to_markdown(index=False)
            formatted_content = (
                f"### File Content: {file_path.name}\n\n" f"{md_table}\n"
            )

            return {
                "success": True,
                "content": formatted_content,
                "type": "file",
                "text_content": None,
                "text": None,
                "error": None,
                "error_type": None,
            }
        except Exception as e:
            logger.error("Failed to read spreadsheet %s: %s", file_path.name, str(e))
            return self._format_error(
                "spreadsheet_error",
                f"Failed to read spreadsheet {file_path.name}: {str(e)}",
            )

    def _handle_html_file(self, file_path: Path) -> Dict[str, Any]:
        """Handle HTML file conversion.

        Args:
            file_path: Path to the HTML file

        Returns:
            Dictionary containing the conversion results
        """
        try:
            logger.info("Reading HTML file: %s", file_path.name)
            with open(file_path, "r", encoding="utf-8") as f:
                html_content = f.read()

            # Parse HTML and extract text
            soup = BeautifulSoup(html_content, "html.parser")
            text_content = soup.get_text(separator="\n\n")

            formatted_content = (
                f"### File Content: {file_path.name}\n\n" f"{text_content}\n"
            )

            return {
                "success": True,
                "content": formatted_content,
                "type": "file",
                "text_content": None,
                "text": None,
                "error": None,
                "error_type": None,
            }
        except Exception as e:
            logger.error("Failed to read HTML %s: %s", file_path.name, str(e))
            return self._format_error(
                "html_error", f"Failed to read HTML {file_path.name}: {str(e)}"
            )

    def _handle_json_file(self, file_path: Path) -> Dict[str, Any]:
        """Handle JSON file conversion.

        Args:
            file_path: Path to the JSON file

        Returns:
            Processed JSON content
        """
        try:
            with open(file_path, "r") as f:
                data = json.load(f)
                # Pretty print the JSON with proper indentation
                formatted_json = json.dumps(data, indent=2)
                content = f"```json\n{formatted_json}\n```"
                return {
                    "success": True,
                    "content": self._format_file_content(content, file_path.name),
                    "type": "json",
                    "text_content": None,
                    "text": None,
                    "error": None,
                    "error_type": None,
                }
        except json.JSONDecodeError as e:
            return self._format_error(
                "json_parse_error", f"Invalid JSON file: {str(e)}"
            )
        except Exception as e:
            return self._format_error(
                "file_error", f"Error reading JSON file: {str(e)}"
            )

    def _handle_document_file(self, file_path: Path) -> Dict[str, Any]:
        """Handle document file conversion.

        Args:
            file_path: Path to the document file

        Returns:
            Dictionary containing the conversion results
        """
        try:
            # Use MarkItDown's built-in document handling
            result = self.markitdown.convert_document(str(file_path))
            return {
                "success": True,
                "content": self._format_file_content(result, file_path.name),
                "type": "document",
                "text_content": None,
                "text": None,
                "error": None,
                "error_type": None,
            }
        except Exception as e:
            logger.error("Failed to read document %s: %s", file_path.name, str(e))
            return self._format_error(
                "document_error", f"Failed to read document {file_path.name}: {str(e)}"
            )

    def _handle_text_file(self, file_path: Path) -> Dict[str, Any]:
        """Handle text file conversion.

        Args:
            file_path: Path to the text file

        Returns:
            Dictionary containing the conversion results
        """
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
                except Exception as e:
                    last_error = e
                    break

            if content is None:
                raise last_error or Exception(
                    "Failed to read text file with any encoding"
                )

            # Format as markdown code block
            formatted_content = f"```\n{content}\n```"
            return {
                "success": True,
                "content": self._format_file_content(formatted_content, file_path.name),
                "type": "text",
                "text_content": None,
                "text": None,
                "error": None,
                "error_type": None,
            }

        except Exception as e:
            logger.error("Failed to read text file %s: %s", file_path.name, str(e))
            return self._format_error(
                "text_error", f"Failed to read text file {file_path.name}: {str(e)}"
            )
