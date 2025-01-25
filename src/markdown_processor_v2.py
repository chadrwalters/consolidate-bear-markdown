"""Simplified markdown processor with unified reference handling."""

import logging
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, TypedDict, Union, cast
from urllib.parse import urlparse

from tqdm import tqdm  # type: ignore

from .converter_factory import ConverterFactory
from .file_manager import FileManager
from .file_system import FileSystem, MarkdownFile
from .reference_match import ReferenceMatch, find_markdown_references
from .processing_stats import ProcessingStats, ErrorType
from .logging_utils import log_timing, log_block_timing
from .progress_manager import ProgressManager
from .console_manager import ConsoleManager

logger = logging.getLogger(__name__)


class ConversionResult(TypedDict, total=False):
    """Result of a conversion operation."""
    text: str
    text_content: str
    content: str
    type: str


class AttachmentProcessingResult(TypedDict):
    """Result of processing an attachment."""
    success: bool
    error: Optional[str]
    error_type: Optional[str]
    text: Optional[str]
    text_content: Optional[str]
    content: Optional[str]
    type: Optional[str]


class ProcessingResult(TypedDict):
    """Result of processing a markdown file."""
    success: bool
    error: Optional[str]
    content: Optional[str]
    attachments: List[AttachmentProcessingResult]


class MarkdownProcessorV2:
    """Processes markdown files with unified reference handling."""

    def __init__(
        self,
        converter_factory: ConverterFactory,
        file_system: FileSystem,
        src_dir: Path,
        dest_dir: Path,
        force_generation: bool = False,
        config: Dict = {},
    ):
        """Initialize the markdown processor.

        Args:
            converter_factory: The converter factory instance
            file_system: The file system handler
            src_dir: Source directory containing markdown files
            dest_dir: Destination directory for processed files
            force_generation: Whether to force regeneration of all files
            config: Configuration dictionary
        """
        self.converter_factory = converter_factory
        self.file_system = file_system
        self.src_dir = src_dir
        self.dest_dir = dest_dir
        self.force_generation = force_generation
        self.config = config
        self.no_image = config.get("no_image", False)
        self.progress: Optional[ProgressManager] = None
        self.stats = ProcessingStats()

        # Setup console and logging
        self.console = ConsoleManager(
            cbm_dir=config.get("cbm_dir", ".cbm"),
            log_level=config.get("logLevel", "WARNING")
        )
        self.console.setup_logging()

    def _is_external_url(self, path: str) -> bool:
        """Check if a path is an external URL.

        Args:
            path: Path to check

        Returns:
            True if path is an external URL
        """
        try:
            result = urlparse(path)
            return bool(result.scheme and result.netloc)
        except Exception:
            return False

    def should_process(self, md_file: MarkdownFile) -> bool:
        """Determine if a markdown file should be processed.

        A file should be processed if:
        1. Force generation is enabled
        2. Output file doesn't exist
        3. Source file is newer than output
        4. Any attachments are newer than output
        5. Content has changed (only for files without references and no attachment dir)

        Files with references but no attachment directory are skipped.
        Files with references are only processed if they are newer than output.
        Files without references and no attachment dir are always processed.
        Files with attachment dir are treated as having references.
        """
        # Always process if force generation enabled
        if self.force_generation:
            return True

        # Get output file path
        out_file = self.dest_dir / md_file.md_path.name

        # If output doesn't exist, process
        if not out_file.exists():
            return True

        # Get modification times
        src_mtime = md_file.md_path.stat().st_mtime
        out_mtime = out_file.stat().st_mtime

        # Check if source is newer than output
        if src_mtime > out_mtime:
            return True

        # Check if any attachments are newer than output
        if md_file.attachment_dir:
            for attachment in self.file_system.get_attachments(md_file.attachment_dir):
                if attachment.stat().st_mtime > out_mtime:
                    return True

        # Check for references in the file
        content = md_file.md_path.read_text()
        refs = find_markdown_references(content)

        # If file has references but no attachment directory, skip it
        if refs and not md_file.attachment_dir:
            return False

        # For files without references and no attachment dir, always process
        if not refs and not md_file.attachment_dir:
            return True

        # File has references or attachment dir but is not newer than output
        return False

    @log_timing
    def _process_attachment(
        self,
        attachment_path: Path,
    ) -> AttachmentProcessingResult:
        """Process a single attachment file.

        Args:
            attachment_path: Path to the attachment file

        Returns:
            Dictionary containing the processing results
        """
        # Handle external URLs
        if isinstance(attachment_path, str) and self._is_external_url(attachment_path):
            return AttachmentProcessingResult(
                success=False,
                error="External URL",
                error_type="external_url",
                text=None,
                text_content=None,
                content=None,
                type=None
            )

        try:
            converter = self.converter_factory.get_converter(attachment_path)
            if converter is None:
                return AttachmentProcessingResult(
                    success=False,
                    error=f"No converter found for {attachment_path.suffix}",
                    error_type="unsupported_type",
                    text=None,
                    text_content=None,
                    content=None,
                    type=None
                )

            result = converter.convert(attachment_path)
            # Cast the result to ConversionResult to ensure type safety
            typed_result = cast(ConversionResult, result)
            return AttachmentProcessingResult(
                success=True,
                error=None,
                error_type=None,
                text=typed_result.get("text"),
                text_content=typed_result.get("text_content"),
                content=typed_result.get("content"),
                type=typed_result.get("type")
            )
        except Exception as e:
            return AttachmentProcessingResult(
                success=False,
                error=str(e),
                error_type="processing_error",
                text=None,
                text_content=None,
                content=None,
                type=None
            )

    def _update_reference_with_error(
        self,
        content: str,
        ref: ReferenceMatch,
        error: Optional[str],
        error_type: Optional[str]
    ) -> str:
        """Update a reference in the content with an error message."""
        if ref.link_path.startswith(("http://", "https://")):
            error_comment = "<!-- Error: External URL skipped -->"
        elif error == "File not found":
            error_comment = "<!-- File not found -->"
        else:
            error_comment = f"<!-- Error: {error or 'Unknown error'} -->"

        return content.replace(ref.original_text, f"{ref.original_text}\n{error_comment}")

    def _find_embedded_references(self, md_path: Path) -> List[ReferenceMatch]:
        """Find embedded references in a markdown file."""
        with open(md_path, 'r') as f:
            content = f.read()
        return [ref for ref in find_markdown_references(content) if ref.embed]

    @log_timing
    def process_markdown_file(self, md_file: MarkdownFile) -> Optional[dict]:
        """Process a single markdown file.

        Args:
            md_file: The markdown file to process.

        Returns:
            A dictionary containing processing statistics or None if the file was skipped.
        """
        try:
            logging.debug(f"Processing file: {md_file.md_path}")

            # Check if file should be processed
            if not self.should_process(md_file):
                logging.debug(f"Skipping file: {md_file.md_path}")
                self.stats.record_skipped(str(md_file.md_path))
                return None

            # Read content and find embedded references
            try:
                content = md_file.md_path.read_text()
            except Exception as e:
                self.stats.record_error(str(md_file.md_path), f"Failed to read file: {str(e)}")
                return None

            refs = find_markdown_references(content)

            if not refs:
                logging.debug(f"File has no references, copying to destination: {md_file.md_path}")
                out_file = self.dest_dir / md_file.md_path.name
                out_file.parent.mkdir(parents=True, exist_ok=True)
                out_file.write_text(content)
                self.stats.record_processed(str(md_file.md_path))
                return {
                    "total_attachments": 0,
                    "success_attachments": 0,
                    "error_attachments": 0,
                    "skipped_attachments": 0
                }

            # Process embedded references
            total_attachments = 0
            success_attachments = 0
            error_attachments = 0
            skipped_attachments = 0
            has_local_attachments = False

            for ref in refs:
                # Skip external URLs
                if ref.link_path.startswith(("http://", "https://")):
                    content = self._update_reference_with_error(
                        content, ref, "External URL skipped", "external_url"
                    )
                    self.stats.record_external_url()
                    continue

                # Get attachment path
                attachment_path = md_file.get_attachment(ref.link_path)
                if not attachment_path:
                    content = self._update_reference_with_error(
                        content, ref, "File not found", "file_not_found"
                    )
                    error_attachments += 1
                    has_local_attachments = True
                    continue

                # Process the attachment
                total_attachments += 1
                has_local_attachments = True
                result = self._process_attachment(attachment_path)

                if result["success"]:
                    content = self._update_reference_with_success(content, ref, result)
                    success_attachments += 1
                else:
                    content = self._update_reference_with_error(
                        content, ref, result["error"], result.get("error_type", "unknown")
                    )
                    error_attachments += 1

            # Write processed content
            out_file = self.dest_dir / md_file.md_path.name
            out_file.parent.mkdir(parents=True, exist_ok=True)
            out_file.write_text(content)

            if has_local_attachments:
                self.stats.record_processed(str(md_file.md_path))
            else:
                self.stats.record_unchanged(str(md_file.md_path))

            return {
                "total_attachments": total_attachments,
                "success_attachments": success_attachments,
                "error_attachments": error_attachments,
                "skipped_attachments": skipped_attachments
            }

        except Exception as e:
            self.stats.record_error(str(md_file.md_path), str(e))
            logging.error(f"Error processing {md_file.md_path}: {str(e)}")
            return None

    def process_attachment(
        self,
        md_file: Path,
        attachment_path: Path,
    ) -> AttachmentProcessingResult:
        """Process a single attachment file.

        Args:
            md_file: Path to the markdown file containing the attachment
            attachment_path: Path to the attachment file

        Returns:
            Result of processing the attachment
        """
        return self._process_attachment(attachment_path)

    @log_timing
    def process_all(self) -> None:
        """Process all markdown files in the source directory."""
        # Find all markdown files
        md_files = list(self.file_system.discover_markdown_files())
        logging.info(f"Found {len(md_files)} markdown files to process")

        # Process each file
        with tqdm(md_files, desc="Processing Markdown Files") as pbar:
            for md_file in pbar:
                logging.debug(f"Processing file: {md_file.md_path}")
                result = self.process_markdown_file(md_file)
                logging.debug(f"File stats: {result}")

        # Log final statistics
        stats = self.stats.get_statistics()
        logging.debug(f"Final stats: {stats}")

    def cleanup(self) -> None:
        """Clean up resources."""
        try:
            if hasattr(self, "converter_factory"):
                # Clean up any converter resources
                for converter in self.converter_factory.converters:
                    if hasattr(converter, "cleanup"):
                        try:
                            converter.cleanup()
                        except Exception as e:
                            logger.debug(f"Error cleaning up converter: {e}")
        except Exception as e:
            logger.debug(f"Error during cleanup: {e}")

    def __del__(self) -> None:
        """Clean up on deletion."""
        try:
            self.cleanup()
        except Exception as e:
            # Use module-level logger since instance might be partially deleted
            logger.debug(f"Error during cleanup: {e}")

    def format_stats(self) -> str:
        """Format statistics for display.

        Returns:
            Formatted statistics string
        """
        return str(self.stats)

    def _format_error_block(self, ref_path: str, error_msg: str) -> str:
        """Format error block for markdown.

        Args:
            ref_path: Reference path that failed
            error_msg: Error message

        Returns:
            Formatted error block
        """
        return f"\n\n<!-- Error processing {ref_path}: {error_msg} -->\n"

    def _format_embedded_content(
        self, ref_text: str, alt_text: Optional[str], content: str
    ) -> str:
        """Format embedded content block.

        Args:
            ref_text: Original reference text
            alt_text: Alternative text for summary
            content: Content to embed

        Returns:
            Formatted content block
        """
        summary = alt_text or "Embedded content"
        return (
            f"{ref_text}\n"
            f"<details>\n"
            f"<summary>{summary}</summary>\n\n"
            f"{content}\n\n"
            f"</details>\n"
        )

    def _format_summary_table(self) -> str:
        """Format processing statistics into a table.

        Returns:
            Formatted table string
        """
        stats = self.stats.get_statistics()
        total_files = (stats["files_processed"] + stats["files_errored"] +
                      stats["files_skipped"] + stats["files_unchanged"])
        # Don't include external URLs in total attachments
        total_attachments = stats["total_attachments"]

        # Format the table with consistent spacing
        table = (
            "─────────────────────────────────────────────────\n"
            "                Processing Summary                \n"
            "────────────────────┬────────────────────────────\n"
            " Files              │ Attachments                \n"
            "────────────────────┼────────────────────────────\n"
            f" Total:      {total_files:3d}   │ Total:      {total_attachments:3d}        \n"
            f" Processed:  {stats['files_processed']:3d}   │ Processed:  {stats['success_attachments']:3d}        \n"
            f" Errors:     {stats['files_errored']:3d}   │ Errors:     {stats['error_attachments']:3d}        \n"
            f" Skipped:    {stats['files_skipped']:3d}   │ Skipped:    {stats['skipped_attachments']:3d}        \n"
            f" Unchanged:  {stats['files_unchanged']:3d}   │ External:   {stats['external_urls']:3d}        \n"
            "─────────────────────────────────────────────────"
        )

        return table

    def _update_reference_with_success(
        self,
        content: str,
        ref: ReferenceMatch,
        result: AttachmentProcessingResult
    ) -> str:
        """Update a reference with successful conversion result."""
        if result["content"] is None:
            return content
        return content.replace(ref.original_text, result["content"])

    def _process_attachment_reference(self, md_file: MarkdownFile, ref: ReferenceMatch) -> AttachmentProcessingResult:
        """Process a single attachment reference."""
        logging.debug(f"Converting attachment: {ref.link_path}")

        # Get the attachment path
        attachment_path = md_file.get_attachment(ref.link_path)
        if not attachment_path:
            return AttachmentProcessingResult(
                success=False,
                error="File not found",
                error_type="file_not_found",
                text=None,
                text_content=None,
                content=None,
                type=None
            )

        # Process the attachment
        result = self._process_attachment(attachment_path)
        return result
