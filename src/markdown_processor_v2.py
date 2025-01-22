"""Simplified markdown processor with unified reference handling."""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, TypedDict

from tqdm import tqdm  # type: ignore

from .converter_factory import ConverterFactory
from .file_manager import FileManager
from .file_system import FileSystem, MarkdownFile
from .reference_match import find_markdown_references

logger = logging.getLogger(__name__)


class AttachmentResult(TypedDict):
    """Result of processing an attachment."""

    success: bool
    error: Optional[str]
    content: Optional[str]


class MarkdownProcessorV2:
    """Processes markdown files with unified reference handling."""

    def __init__(
        self,
        converter_factory: ConverterFactory,
        file_system: FileSystem,
        src_dir: Path,
        dest_dir: Path,
    ):
        """Initialize the markdown processor.

        Args:
            converter_factory: The converter factory instance
            file_system: The file system handler
            src_dir: Source directory containing markdown files
            dest_dir: Destination directory for processed files
        """
        self.converter_factory = converter_factory
        self.fs = file_system
        self.src_dir = src_dir
        self.dest_dir = dest_dir
        self.logger = logger
        self.file_manager = FileManager(self.fs.cbm_dir, src_dir, dest_dir)
        self.stats = ProcessingStats()

    def process_attachment(
        self, md_file: Path, attachment_path: Path
    ) -> Dict[str, Any]:
        """Process a single attachment file.

        Args:
            md_file: Path to the markdown file containing the attachment
            attachment_path: Path to the attachment file

        Returns:
            Dictionary containing the processing results
        """
        logger.info("Converting attachment: %s", attachment_path.name)

        # Check if file exists
        if not attachment_path.exists():
            error_msg = f"File not found: {attachment_path.name}"
            logger.error(error_msg)
            self.stats.record_error("file_not_found", str(attachment_path), error_msg)
            return {
                "success": False,
                "content": None,
                "error": error_msg,
                "error_type": "file_not_found",
                "type": "unknown",
                "text_content": None,
                "text": None,
            }

        try:
            result = self.converter_factory.convert_file(attachment_path)
            if result.get("success", False):
                self.stats.record_success()
            else:
                error_type = result.get("error_type") or "conversion_error"
                error_msg = result.get("error") or "Unknown conversion error"
                self.stats.record_error(error_type, str(attachment_path), error_msg)
            return dict(result)  # Convert TypedDict to regular dict

        except Exception as e:
            error_msg = f"Failed to process attachment: {str(e)}"
            logger.error(error_msg)
            self.stats.record_error("processing_error", str(attachment_path), error_msg)
            return {
                "success": False,
                "content": None,
                "error": error_msg,
                "error_type": "processing_error",
                "type": "unknown",
                "text_content": None,
                "text": None,
            }

    def process_markdown_file(
        self, md_file: MarkdownFile
    ) -> Tuple[str, Dict[str, int]]:
        """Process a markdown file and its references.

        This function processes each reference in the markdown file, replacing
        references with their embedded content where appropriate.

        Args:
            md_file: The markdown file to process

        Returns:
            Tuple of (processed content, statistics)
        """
        stats = {"success": 0, "error": 0, "missing": 0, "skipped": 0}

        try:
            content = md_file.md_path.read_text()
            references = find_markdown_references(content)

            # Create progress bar for attachments
            with tqdm(
                total=len(references),
                desc=f"Processing {md_file.md_path.name}",
                leave=False,
            ) as pbar:
                for ref in references:
                    # Skip non-embedded references (including images with embed=false)
                    if not ref.embed:
                        stats["skipped"] += 1
                        pbar.update(1)
                        continue

                    if not md_file.attachment_dir:
                        logger.warning(
                            "Missing attachment directory for file: %s", md_file.md_path
                        )
                        stats["skipped"] += 1
                        pbar.update(1)
                        continue

                    # Get the attachment using the reference path
                    attachment_path = md_file.get_attachment(ref.link_path)
                    if not attachment_path:
                        logger.warning(
                            "Missing attachment: %s referenced in %s",
                            ref.link_path,
                            md_file.md_path,
                        )
                        stats["skipped"] += 1
                        pbar.update(1)
                        continue

                    # Normalize the attachment path
                    attachment_path = self.file_manager.normalize_path(attachment_path)
                    if not self.file_manager.validate_path(attachment_path):
                        stats["error"] += 1
                        error_block = self._format_error_block(
                            ref.link_path, "Invalid or inaccessible path"
                        )
                        content = content.replace(
                            ref.original_text, f"{ref.original_text}{error_block}"
                        )
                        pbar.update(1)
                        continue

                    # Process the attachment
                    result = self.process_attachment(md_file.md_path, attachment_path)
                    if result["success"]:
                        # Create embedded content section
                        embedded_content = self._format_embedded_content(
                            ref.original_text, ref.alt_text, result["content"]
                        )
                        # Add embedded content after the reference
                        content = content.replace(
                            ref.original_text, f"{ref.original_text}{embedded_content}"
                        )
                        stats["success"] += 1
                    else:
                        stats["error"] += 1
                        error_block = self._format_error_block(
                            ref.link_path, result.get("error", "Unknown error")
                        )
                        content = content.replace(
                            ref.original_text, f"{ref.original_text}{error_block}"
                        )

                    pbar.update(1)

            return content, stats

        except Exception as e:
            self.logger.error(f"Error processing markdown file {md_file.md_path}: {e}")
            raise

    def process_all(self) -> Dict[str, int]:
        """Process all markdown files in the source directory.

        Returns:
            Dictionary of processing statistics
        """
        total_stats: Dict[str, Any] = {
            "files_processed": 0,
            "files_errored": 0,
            "success": 0,
            "error": 0,
            "missing": 0,
            "skipped": 0,
            "errors": [],
        }

        try:
            # Get list of markdown files
            md_files = list(self.fs.discover_markdown_files(self.src_dir))

            # Create progress bar for files
            with tqdm(
                total=len(md_files), desc="Processing markdown files", unit="file"
            ) as pbar:
                for md_file in md_files:
                    try:
                        # Create output directory if it doesn't exist
                        output_path = self.dest_dir / md_file.md_path.relative_to(
                            self.src_dir
                        )
                        output_path.parent.mkdir(parents=True, exist_ok=True)

                        # Process the file
                        content, stats = self.process_markdown_file(md_file)
                        output_path.write_text(content)

                        # Update statistics
                        total_stats["files_processed"] += 1
                        for key in ["success", "error", "missing", "skipped"]:
                            total_stats[key] += stats[key]

                        # Update ProcessingStats
                        self.stats.update_file_stats(
                            total=sum(stats.values()),  # Total attachments in file
                            success=stats["success"],
                            error=stats["error"],
                            skipped=stats["skipped"] + stats["missing"],
                        )

                    except Exception as e:
                        self.logger.error(f"Error processing {md_file.md_path}: {e}")
                        total_stats["files_errored"] += 1
                        if isinstance(total_stats["errors"], list):
                            total_stats["errors"].append(str(e))
                        # Update ProcessingStats for failed file
                        self.stats.update_file_stats(
                            total=0, success=0, error=0, skipped=0
                        )

                    finally:
                        pbar.update(1)

            # Convert to Dict[str, int] by removing the errors list
            result: Dict[str, int] = {
                k: v for k, v in total_stats.items() if k != "errors"
            }
            return result

        except Exception as e:
            self.logger.error(f"Error during batch processing: {e}")
            raise

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
        """Format processing statistics as a string.

        Returns:
            Formatted statistics string
        """
        total_files = self.stats.total_files
        success_files = self.stats.success_files
        error_files = self.stats.error_files
        skipped_files = self.stats.skipped_files
        total_attachments = self.stats.total_attachments
        success_attachments = self.stats.success_attachments
        error_attachments = self.stats.error_attachments
        skipped_attachments = self.stats.skipped_attachments

        # Get error breakdown
        error_counts = self.stats.get_error_counts()
        error_breakdown = "\n".join(
            f"│ │ {err_type:15} │ {count:7d} │"
            for err_type, count in error_counts.items()
        )

        return (
            self._format_summary(
                total_files,
                success_files,
                error_files,
                skipped_files,
                total_attachments,
                success_attachments,
                error_attachments,
                skipped_attachments,
            )
            + f"""
│                                                                              │
│                 Error Breakdown                                              │
│ ┏━━━━━━━━━━━━━━━━━━━┳━━━━━━━┓                                              │
│ ┃ Error Type        ┃ Count ┃                                              │
│ ┡━━━━━━━━━━━━━━━━━━━╇━━━━━━━┩                                              │
{error_breakdown}
│ └─────────────────────┴───────┘                                              │
╰──────────────────────────────────────────────────────────────────────────────╯"""
        )

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

    def _format_summary(
        self,
        total_files: int,
        success_files: int,
        error_files: int,
        skipped_files: int,
        total_attachments: int,
        success_attachments: int,
        error_attachments: int,
        skipped_attachments: int,
    ) -> str:
        """Format processing summary."""
        border = "─" * 40
        header = (
            f"╭{border}─ Processing Complete ─{border}╮\n"
            f"│             Processing Summary                               │\n"
            f"│ ┏━━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━━┳━━━━━━━┳━━━━━━━━━┓      │\n"
            f"│ ┃ Category    ┃ Total ┃ Success ┃ Error ┃ Skipped ┃      │\n"
            f"│ ┡━━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━━╇━━━━━━━╇━━━━━━━━━┩      │\n"
        )

        files_row = (
            f"│ │ Files       │ {total_files:5d} │ {success_files:7d} │ "
            f"{error_files:5d} │ {skipped_files:7d} │      │\n"
        )

        attachments_row = (
            f"│ │ Attachments │ {total_attachments:5d} │ {success_attachments:7d} │ "
            f"{error_attachments:5d} │ {skipped_attachments:7d} │      │\n"
        )

        footer = (
            f"│ └─────────────┴───────┴─────────┴───────┴─────────┘      │\n"
            f"╰{border}──────────────────────{border}╯\n"
        )

        return header + files_row + attachments_row + footer


class ProcessingStats:
    """Track processing statistics."""

    def __init__(self) -> None:
        """Initialize statistics."""
        self.total_files = 0
        self.success_files = 0
        self.error_files = 0
        self.skipped_files = 0
        self.total_attachments = 0
        self.success_attachments = 0
        self.error_attachments = 0
        self.skipped_attachments = 0
        self.error_types: Dict[str, int] = {}
        self.error_details: List[Dict[str, str]] = []

    def record_success(self) -> None:
        """Record a successful conversion."""
        self.success_attachments += 1

    def record_error(
        self,
        error_type: str,
        file_path: Optional[str] = None,
        error_msg: Optional[str] = None,
    ) -> None:
        """Record an error.

        Args:
            error_type: Type of error that occurred
            file_path: Path to the file that had the error
            error_msg: Detailed error message
        """
        self.error_attachments += 1
        self.error_types[error_type] = self.error_types.get(error_type, 0) + 1

        if file_path and error_msg:
            self.error_details.append(
                {"file": file_path, "error_type": error_type, "error": error_msg}
            )

    def get_error_details(self) -> List[Dict[str, str]]:
        """Get list of error details.

        Returns:
            List of dictionaries containing error details
        """
        return self.error_details

    def get_error_counts(self) -> Dict[str, int]:
        """Get counts of each error type.

        Returns:
            Dictionary mapping error types to their counts
        """
        return dict(self.error_types)

    def update_file_stats(
        self, total: int, success: int, error: int, skipped: int
    ) -> None:
        """Update file statistics.

        Args:
            total: Total number of attachments
            success: Number of successful conversions
            error: Number of errors
            skipped: Number of skipped attachments
        """
        self.total_files += 1
        self.total_attachments += total
        self.skipped_attachments += skipped

        # A file is successful if it has no errors, regardless of attachments
        if error > 0:
            self.error_files += 1
        else:
            self.success_files += 1

    def get_error_summary(self) -> str:
        """Get error type summary.

        Returns:
            Formatted error summary string
        """
        if not self.error_types:
            return "No errors occurred."

        summary = ["Error type breakdown:"]
        for error_type, count in sorted(self.error_types.items()):
            summary.append(f"  - {error_type}: {count}")
        return "\n".join(summary)
