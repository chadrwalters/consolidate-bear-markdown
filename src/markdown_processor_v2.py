"""Simplified markdown processor with unified reference handling."""

import logging
from pathlib import Path
from typing import Dict, Optional, Tuple, Any, TypedDict

from .markitdown_wrapper import MarkItDownWrapper
from .file_system import FileSystem, MarkdownFile
from .reference_match import find_markdown_references
from .file_manager import FileManager

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
        markitdown: MarkItDownWrapper,
        file_system: FileSystem,
        src_dir: Path,
        dest_dir: Path,
    ):
        """Initialize the markdown processor.

        Args:
            markitdown: The MarkItDown wrapper instance
            file_system: The file system handler
            src_dir: Source directory containing markdown files
            dest_dir: Destination directory for processed files
        """
        self.markitdown = markitdown
        self.fs = file_system
        self.src_dir = src_dir
        self.dest_dir = dest_dir
        self.logger = logger
        self.file_manager = FileManager(self.fs.cbm_dir, src_dir, dest_dir)
        self.stats = ProcessingStats()

    def process_attachment(self, md_file: Path, attachment_path: Path) -> Dict[str, Any]:
        """Process a single attachment file.

        Args:
            md_file: Path to the markdown file containing the attachment
            attachment_path: Path to the attachment file

        Returns:
            Dictionary containing the processing results
        """
        logger.info("Converting attachment: %s", attachment_path.name)
        try:
            result = self.markitdown.convert_file(attachment_path)
            if not result["success"]:
                error_msg = result.get("error", "Unknown error")
                error_type = result.get("error_type", "unknown")
                logger.error("Error converting attachment %s: %s", attachment_path.name, error_msg)
                self.stats.record_error(error_type)
                return {
                    "success": False,
                    "content": f"\n<!-- Error processing {attachment_path.name}: {error_msg} -->\n",
                    "error": error_msg,
                    "error_type": error_type
                }

            self.stats.record_success()
            return result

        except Exception as e:
            logger.error("Failed to process attachment %s: %s", attachment_path.name, str(e))
            self.stats.record_error("system_error")
            return {
                "success": False,
                "content": f"\n<!-- Error processing {attachment_path.name}: {str(e)} -->\n",
                "error": str(e),
                "error_type": "system_error"
            }

    def process_markdown_file(self, md_file: MarkdownFile) -> Tuple[str, Dict[str, int]]:
        """Process a markdown file and its references.

        Args:
            md_file: The markdown file to process

        Returns:
            Tuple of (processed content, statistics)
        """
        stats = {
            "success": 0,
            "error": 0,
            "missing": 0,
            "skipped": 0
        }

        try:
            content = md_file.md_path.read_text()
            references = find_markdown_references(content)

            for ref in references:
                if not ref.embed:
                    stats["skipped"] += 1
                    continue

                if not md_file.attachment_dir:
                    logger.warning("Missing attachment directory for file: %s", md_file.md_path)
                    stats["missing"] += 1
                    continue

                # Get the attachment using the reference path
                attachment_path = md_file.get_attachment(ref.link_path)
                if not attachment_path:
                    logger.warning("Missing attachment: %s referenced in %s", ref.link_path, md_file.md_path)
                    stats["missing"] += 1
                    continue

                # Normalize the attachment path
                attachment_path = self.file_manager.normalize_path(attachment_path)
                if not self.file_manager.validate_path(attachment_path):
                    stats["error"] += 1
                    error_block = f"\n\n<!-- Error processing {ref.link_path}: Invalid or inaccessible path -->\n"
                    content = content.replace(ref.original_text, f"{ref.original_text}{error_block}")
                    continue

                # Process the attachment
                result = self.process_attachment(md_file.md_path, attachment_path)
                if result["success"]:
                    # Create embedded content section
                    embedded_content = f"\n\n<details><summary>{ref.alt_text or 'Embedded content'}</summary>\n\n{result['content']}\n\n</details>\n"
                    # Replace the original reference with reference + embedded content
                    content = content.replace(ref.original_text, f"{ref.original_text}{embedded_content}")
                    stats["success"] += 1
                else:
                    stats["error"] += 1
                    error_block = f"\n\n<!-- Error processing {ref.link_path}: {result['error']} -->\n"
                    content = content.replace(ref.original_text, f"{ref.original_text}{error_block}")

            return content, stats

        except Exception as e:
            self.logger.error(f"Error processing markdown file {md_file.md_path}: {e}")
            raise

    def process_all(self) -> Dict[str, int]:
        """Process all markdown files in the source directory.

        Returns:
            Dictionary of processing statistics
        """
        total_stats = {
            "files_processed": 0,
            "files_errored": 0,
            "success": 0,
            "error": 0,
            "missing": 0,
            "skipped": 0
        }

        try:
            for md_file in self.fs.discover_markdown_files(self.src_dir):
                try:
                    # Create output directory if it doesn't exist
                    output_path = self.dest_dir / md_file.md_path.relative_to(self.src_dir)
                    output_path.parent.mkdir(parents=True, exist_ok=True)

                    # Process the file
                    content, stats = self.process_markdown_file(md_file)
                    output_path.write_text(content)

                    # Update statistics
                    total_stats["files_processed"] += 1
                    for key in ["success", "error", "missing", "skipped"]:
                        total_stats[key] += stats[key]

                except Exception as e:
                    self.logger.error(f"Error processing {md_file.md_path}: {e}")
                    total_stats["files_errored"] += 1

            return total_stats

        except Exception as e:
            self.logger.error(f"Error during batch processing: {e}")
            raise

    def __del__(self) -> None:
        """Clean up resources when the processor is deleted."""
        try:
            self.file_manager.cleanup()
        except Exception as e:
            self.logger.warning(f"Error during cleanup: {e}")

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
        error_breakdown = "\n".join(f"│ {err_type:12} │ {count:7d} │" for err_type, count in error_counts.items())

        return f"""╭──────────────────────────── Processing Complete ─────────────────────────────╮
│                 Processing Summary                                           │
│ ┏━━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━━┳━━━━━━━┳━━━━━━━━━┓                          │
│ ┃ Category    ┃ Total ┃ Success ┃ Error ┃ Skipped ┃                          │
│ ┡━━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━━╇━━━━━━━╇━━━━━━━━━┩                          │
│ │ Files       │ {total_files:5d} │ {success_files:7d} │ {error_files:5d} │ {skipped_files:7} │                          │
│ │ Attachments │ {total_attachments:5d} │ {success_attachments:7d} │ {error_attachments:5d} │ {skipped_attachments:7d} │                          │
│ └─────────────┴───────┴─────────┴───────┴─────────┘                          │
│                                                                              │
│                 Error Breakdown                                              │
│ ┏━━━━━━━━━━━━━┳━━━━━━━┓                                                     │
│ ┃ Error Type  ┃ Count ┃                                                     │
│ ┡━━━━━━━━━━━━━╇━━━━━━━┩                                                     │
{error_breakdown}
│ └─────────────┴───────┘                                                     │
╰──────────────────────────────────────────────────────────────────────────────╯"""

class ProcessingStats:
    """Track processing statistics."""

    def __init__(self):
        """Initialize statistics."""
        self.total_files = 0
        self.success_files = 0
        self.error_files = 0
        self.skipped_files = 0
        self.total_attachments = 0
        self.success_attachments = 0
        self.error_attachments = 0
        self.skipped_attachments = 0
        self.error_counts: Dict[str, int] = {}

    def record_success(self):
        """Record a successful conversion."""
        self.success_attachments += 1

    def record_error(self, error_type: str):
        """Record a conversion error.

        Args:
            error_type: Type of error that occurred
        """
        self.error_attachments += 1
        self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1

    def record_skip(self):
        """Record a skipped conversion."""
        self.skipped_attachments += 1

    def get_error_counts(self) -> Dict[str, int]:
        """Get counts of different error types.

        Returns:
            Dictionary mapping error types to counts
        """
        return dict(sorted(self.error_counts.items()))
