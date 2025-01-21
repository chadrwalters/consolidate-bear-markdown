"""MarkItDown wrapper with standardized output formats."""

import base64
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional, List, Union, TypedDict, cast
import pandas as pd
import xml.dom.minidom
import shutil
from PIL import Image
import json

from .image_cache import ImageCache
from .image_converter import ImageConverter
from openai import OpenAI
from openai.types.chat import (
    ChatCompletionUserMessageParam,
    ChatCompletionMessageParam
)
from markitdown import MarkItDown, UnsupportedFormatException  # type: ignore
from bs4 import BeautifulSoup

import fitz

logger = logging.getLogger(__name__)
# Configure OpenAI loggers to not show debug messages
logging.getLogger("openai").setLevel(logging.INFO)
logging.getLogger("openai._base_client").setLevel(logging.INFO)

class DocumentConverterResult(TypedDict, total=False):
    """Type hints for MarkItDown conversion result."""
    text_content: Optional[str]
    content: Optional[str]
    text: Optional[str]
    success: bool
    error: Optional[str]
    type: str

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

    def convert_file(self, file_path: Path) -> Dict[str, Any]:
        """Convert a file to markdown format.

        Args:
            file_path: Path to the file to convert

        Returns:
            Dictionary containing the conversion results
        """
        try:
            logger.debug("Starting conversion for file: %s", file_path)

            # Handle JSON files directly
            if file_path.suffix.lower() == '.json':
                logger.debug("Detected JSON file, using _handle_json_file")
                return self._handle_json_file(file_path)

            # Handle image files separately for GPT-4o analysis
            image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.heic', '.heif', '.svg'}
            if file_path.suffix.lower() in image_extensions:
                logger.debug("Detected image file, using _handle_image_file")
                return self._handle_image_file(file_path)

            # Use MarkItDown for everything else
            logger.info("Using MarkItDown for %s", file_path.name)
            try:
                result: Any = self.markitdown.convert(str(file_path))

                # Try text_content first (newer MarkItDown versions)
                if hasattr(result, 'text_content') and result.text_content:
                    logger.info("Successfully converted %s using text_content", file_path.name)
                    return {
                        "success": True,
                        "content": self._format_file_content(cast(str, result.text_content), file_path.name),
                        "type": "file"
                    }

                # Try content attribute (older versions)
                if hasattr(result, 'content') and result.content:
                    logger.info("Successfully converted %s using content", file_path.name)
                    return {
                        "success": True,
                        "content": self._format_file_content(cast(str, result.content), file_path.name),
                        "type": "file"
                    }

                # Try getting raw text (some MarkItDown versions)
                if hasattr(result, 'text') and result.text:
                    logger.info("Successfully converted %s using text", file_path.name)
                    return {
                        "success": True,
                        "content": self._format_file_content(cast(str, result.text), file_path.name),
                        "type": "file"
                    }

                # If MarkItDown returns something empty
                logger.warning("MarkItDown returned no usable content for %s", file_path.name)
                return self._format_cannot_parse(
                    file_path.name,
                    "empty_content",
                    "MarkItDown returned no usable content"
                )

            except UnsupportedFormatException as e:
                logger.warning("MarkItDown does not support format for %s: %s", file_path.name, str(e))
                return self._format_cannot_parse(
                    file_path.name,
                    "unsupported_format",
                    f"Format not supported by MarkItDown: {file_path.suffix}"
                )
            except Exception as e:
                logger.error("MarkItDown conversion error for %s: %s", file_path.name, str(e))
                return self._format_cannot_parse(
                    file_path.name,
                    "conversion_error",
                    f"Failed to convert: {str(e)}"
                )

        except Exception as e:
            logger.error("Conversion error for %s: %s", file_path.name, str(e))
            return self._format_error("system_error", str(e))

    def _format_cannot_parse(self, filename: str, error_type: str = "parse_error", error_msg: str = "Cannot be parsed by MarkItDown.") -> Dict[str, Any]:
        """Format message for files that cannot be parsed by MarkItDown.

        Args:
            filename: Name of the file that couldn't be parsed
            error_type: Type of error (e.g., unsupported_format, parse_error)
            error_msg: Detailed error message

        Returns:
            Error result dictionary
        """
        return {
            "success": False,
            "content": f"### File Content: {filename}\n\n> {error_msg}\n",
            "type": "file",
            "error": error_msg,
            "error_type": error_type
        }

    def _handle_image_file(self, file_path: Path) -> Dict[str, Any]:
        """Handle image file conversion.

        Args:
            file_path: Path to the image file

        Returns:
            Processed image content
        """
        # Check if file exists
        if not file_path.exists():
            return self._format_error(
                "File not found",
                f"Image file {file_path.name} does not exist"
            )

        # Check cache
        if self.image_cache.is_processed(file_path):
            cached_path = self.image_cache.get_cached_path(file_path)
            if cached_path:
                logger.info(f"Using cached analysis for {file_path.name}")
                return {
                    "success": True,
                    "content": self._format_image_analysis(
                        "Using cached analysis",
                        file_path.name
                    ),
                    "type": "image"
                }

        try:
            # Handle SVG files
            if file_path.suffix.lower() == ".svg":
                # Convert SVG to PDF in memory
                doc = fitz.Document(str(file_path))
                if not doc:
                    return self._format_error(
                        "Failed to parse SVG file",
                        "Failed to parse SVG file"
                    )

                # Create PNG file path
                png_path = self.temp_images / f"{file_path.stem}.png"

                # Convert to PNG with high resolution
                page = doc.load_page(0)
                pix = page.get_pixmap(alpha=True, dpi=300)
                pix.save(str(png_path))

                # Save original SVG content for reference
                with open(file_path, "r") as f:
                    svg_content = f.read()

                # Process the converted PNG file
                with open(png_path, "rb") as f:
                    image_data = f.read()
                    base64_image = base64.b64encode(image_data).decode()

                # Get vision description
                message: ChatCompletionMessageParam = {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Please describe this image."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64_image}"
                            }
                        }
                    ]
                }
                response = self.client.chat.completions.create(
                    model="gpt-4o",
                    messages=[message],
                    max_tokens=500
                )
                description = response.choices[0].message.content

                # Return both the description and original SVG
                return {
                    "success": True,
                    "content": self._format_image_analysis(
                        f"{description}\n\n```svg\n{svg_content}\n```",
                        file_path.name
                    ),
                    "type": "image"
                }

            # For other image types, use standard conversion
            converted_path = self.image_converter.convert_if_needed(file_path)
            if not converted_path:
                return {
                    "success": False,
                    "error": f"Could not convert {file_path.name}",
                    "type": "image"
                }

            # Process with GPT-4o
            result = self.process_image(converted_path)
            if not result["success"]:
                return {
                    "success": False,
                    "error": result.get("error", "Unknown error"),
                    "type": "image"
                }

            # Cache result
            self.image_cache.cache_image(file_path)
            self.image_cache.mark_processed(file_path)

            return {
                "success": True,
                "content": self._format_image_analysis(
                    result["text"],
                    file_path.name
                ),
                "type": "image"
            }

        except Exception as e:
            logger.error(f"Failed to process image {file_path.name}: {e}")
            return {
                "success": False,
                "error": str(e),
                "type": "image"
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
                    f"]({original_path})",
                    f"]({processed_path})"
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
                "error": f"Image file not found: {image_path}"
            }

        try:
            # Read image file
            with open(image_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode('utf-8')

            # Process with retries
            for attempt in range(self.max_retries):
                try:
                    messages: List[ChatCompletionMessageParam] = [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "Describe this image in detail."},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{image_data}",
                                        "detail": "high"
                                    }
                                }
                            ]
                        }
                    ]

                    # Avoid logging base64 data
                    logger.debug("Sending request to OpenAI API with image data")
                    response = self.client.chat.completions.create(
                        model="gpt-4o",
                        messages=messages
                    )

                    # Extract and format the response
                    if response and response.choices and response.choices[0].message:
                        description = response.choices[0].message.content or ""
                        return {
                            "success": True,
                            "text": description,
                            "error": None
                        }
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
                "error": f"Failed to process image after {self.max_retries} attempts"
            }

        except Exception as e:
            logger.error(f"Failed to process image {image_path}: {e}")
            return {
                "success": False,
                "content": None,
                "error": str(e)
            }

    def _format_image_analysis(self, analysis: str, image_name: str) -> str:
        """Format image analysis with consistent headers and structure.

        Args:
            analysis: Raw analysis text
            image_name: Name of the image file

        Returns:
            Formatted markdown content
        """
        return (
            f"### Image Analysis: {image_name}\n\n"
            "#### Extracted Content\n\n"
            f"{analysis}\n"
        )

    def _format_file_content(self, content: str, filename: str) -> str:
        """Format file content for embedding.

        Args:
            content: The file content to format
            filename: Name of the file being processed

        Returns:
            Formatted content ready for embedding
        """
        return (
            f"### File Content: {filename}\n\n"
            f"{content}\n"
        )

    def _format_error(self, error_type: str, message: str) -> Dict[str, Any]:
        """Format error messages consistently.

        Args:
            error_type: Type of error
            message: Error message

        Returns:
            Error result dictionary
        """
        return {
            "success": False,
            "content": f"<!-- Error: {error_type} - {message} -->",
            "type": "error",
            "error": message,
            "error_type": error_type
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
            if file_path.suffix.lower() == '.csv':
                df = pd.read_csv(file_path)
            else:  # Excel files
                df = pd.read_excel(file_path)

            # Convert to markdown table
            md_table = df.to_markdown(index=False)
            formatted_content = (
                f"### File Content: {file_path.name}\n\n"
                f"{md_table}\n"
            )

            return {
                "success": True,
                "content": formatted_content,
                "type": "file"
            }
        except Exception as e:
            logger.error("Failed to read spreadsheet %s: %s", file_path.name, str(e))
            return self._format_error(
                f"Failed to read spreadsheet {file_path.name}",
                str(e)
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
            with open(file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()

            # Parse HTML and extract text
            soup = BeautifulSoup(html_content, 'html.parser')
            text_content = soup.get_text(separator='\n\n')

            formatted_content = (
                f"### File Content: {file_path.name}\n\n"
                f"{text_content}\n"
            )

            return {
                "success": True,
                "content": formatted_content,
                "type": "file"
            }
        except Exception as e:
            logger.error("Failed to read HTML %s: %s", file_path.name, str(e))
            return self._format_error(
                f"Failed to read HTML {file_path.name}",
                str(e)
            )

    def _handle_json_file(self, file_path: Path) -> Dict[str, Any]:
        """Handle JSON file conversion.

        Args:
            file_path: Path to the JSON file

        Returns:
            Processed JSON content as markdown
        """
        try:
            # Read and parse JSON
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Convert to pretty JSON string
            pretty_json = json.dumps(data, indent=2)

            # Format as markdown
            content = (
                f"### JSON Content: {file_path.name}\n\n"
                "```json\n"
                f"{pretty_json}\n"
                "```\n"
            )

            return {
                "success": True,
                "content": content,
                "type": "json"
            }

        except json.JSONDecodeError as e:
            logger.error("Invalid JSON in %s: %s", file_path.name, str(e))
            return {
                "success": False,
                "error": f"Invalid JSON: {str(e)}",
                "type": "json"
            }
        except Exception as e:
            logger.error("Error processing JSON file %s: %s", file_path.name, str(e))
            return {
                "success": False,
                "error": str(e),
                "type": "json"
            }
