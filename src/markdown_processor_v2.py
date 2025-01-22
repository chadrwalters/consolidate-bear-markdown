"""Simplified markdown processor with unified reference handling."""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, TypedDict

from tqdm import tqdm  # type: ignore

from .converter_factory import ConverterFactory
from .file_manager import FileManager
from .file_system import FileSystem, MarkdownFile
from .reference_match import ReferenceMatch, find_markdown_references
from .processing_stats import ProcessingStats
from .logging_utils import log_timing, log_block_timing

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
        force_generation: bool = False,
    ):
        """Initialize the markdown processor.

        Args:
            converter_factory: The converter factory instance
            file_system: The file system handler
            src_dir: Source directory containing markdown files
            dest_dir: Destination directory for processed files
            force_generation: Whether to force regeneration of all files
        """
        self.converter_factory = converter_factory
        self.fs = file_system
        self.src_dir = src_dir
        self.dest_dir = dest_dir
        self.force_generation = force_generation
        self.logger = logger
        self.file_manager = FileManager(self.fs.cbm_dir, src_dir, dest_dir)
        self.stats = ProcessingStats()

    def should_process(self, md_file: MarkdownFile) -> bool:
        """Check if a file needs to be processed.

        Args:
            md_file: The markdown file to check

        Returns:
            True if the file should be processed, False otherwise
        """
        if self.force_generation:
            return True

        output_path = self.dest_dir / md_file.md_path.relative_to(self.src_dir)
        if not output_path.exists():
            return True

        output_mtime = output_path.stat().st_mtime
        if md_file.md_path.stat().st_mtime > output_mtime:
            return True

        # Check attachments if directory exists
        if md_file.attachment_dir and md_file.attachment_dir.exists():
            for attach in md_file.attachment_dir.iterdir():
                if not attach.name.startswith("."):
                    if attach.stat().st_mtime > output_mtime:
                        return True

        return False

    @log_timing
    def _process_attachment(
        self,
        attachment_path: Path,
    ) -> dict[str, Any]:
        """Process an attachment file.

        Args:
            attachment_path: Path to the attachment file

        Returns:
            Dictionary containing the processing results
        """
        logger.info("Converting attachment: %s", attachment_path.name)

        # Check if file exists
        if not attachment_path.exists():
            error_msg = f"File not found: {attachment_path.name}"
            logger.error(error_msg)
            self.stats.record_error(str(attachment_path), error_msg)
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
                self.stats.record_success(str(attachment_path))
            else:
                error_msg = result.get("error") or "Unknown conversion error"
                self.stats.record_error(str(attachment_path), error_msg)
            return dict(result)  # Convert TypedDict to regular dict

        except Exception as e:
            error_msg = f"Failed to process attachment: {str(e)}"
            logger.error(error_msg)
            self.stats.record_error(str(attachment_path), error_msg)
            return {
                "success": False,
                "content": None,
                "error": error_msg,
                "error_type": "processing_error",
                "type": "unknown",
                "text_content": None,
                "text": None,
            }

    def _update_reference_with_error(self, content: str, ref: ReferenceMatch, error_msg: str) -> str:
        """Update a reference in the content with an error message.

        Args:
            content: The markdown content to update
            ref: The reference match to update
            error_msg: The error message to add

        Returns:
            The updated content
        """
        return content.replace(
            ref.original_text,
            f"{ref.original_text}\n<!-- Error: {error_msg} -->\n"
        )

    @log_timing
    def process_markdown_file(
        self, md_file: MarkdownFile
    ) -> tuple[str, dict[str, int]]:
        """Process a markdown file and its attachments."""
        stats = ProcessingStats()
        content = md_file.content

        if not md_file.attachment_dir:
            logger.warning(f"Missing attachment directory for file: {md_file.md_path}")
            # Process references even without attachment directory to add error messages
            references = find_markdown_references(content)
            for ref in references:
                if ref.embed:  # Only record errors for embedded references
                    error_msg = "Invalid or inaccessible path: Missing attachment directory"
                    stats.record_error(str(ref.link_path), error_msg)
                    content = self._update_reference_with_error(content, ref, error_msg)
            return content, stats.get_statistics()

        references = find_markdown_references(content)
        for ref in references:
            if not ref.embed:
                stats.record_skipped(str(ref.link_path))
                continue

            with log_block_timing(f"Processing reference: {ref.link_path}"):
                attachment_path = md_file.get_attachment(ref.link_path)
                if not attachment_path:
                    stats.record_skipped(str(ref.link_path))
                    continue

                # Save the current stats instance
                old_stats = self.stats
                self.stats = stats

                result = self._process_attachment(attachment_path)
                if result["success"]:
                    content = content.replace(
                        ref.original_text,
                        f"{ref.original_text}\n{result.get('content', '')}\n"
                    )
                else:
                    content = self._update_reference_with_error(content, ref, result["error"])

                # Restore the old stats instance
                self.stats = old_stats

        return content, stats.get_statistics()

    def process_attachment(
        self,
        md_file: Path,
        attachment_path: Path,
    ) -> dict[str, Any]:
        """Process a single attachment file.

        Args:
            md_file: Path to the markdown file containing the attachment
            attachment_path: Path to the attachment file

        Returns:
            Dictionary containing the processing results
        """
        return self._process_attachment(attachment_path)

    def process_all(self) -> Dict[str, int]:
        """Process all markdown files in the source directory.

        Returns:
            Dictionary of processing statistics
        """
        self.stats = ProcessingStats()  # Reset stats for this run

        try:
            # Get list of markdown files
            md_files = list(self.fs.discover_markdown_files(self.src_dir))

            # Create progress bar for files
            with tqdm(
                total=len(md_files), desc="Processing markdown files", unit="file"
            ) as pbar:
                for md_file in md_files:
                    try:
                        # Check if we need to process this file
                        if not self.should_process(md_file):
                            logger.info(f"Skipping {md_file.md_path} - no changes detected")
                            self.stats.record_unchanged(str(md_file.md_path))
                            pbar.update(1)
                            continue

                        # Create output directory if it doesn't exist
                        output_path = self.dest_dir / md_file.md_path.relative_to(
                            self.src_dir
                        )
                        output_path.parent.mkdir(parents=True, exist_ok=True)

                        # Process the file
                        content, file_stats = self.process_markdown_file(md_file)
                        output_path.write_text(content)

                        # Update statistics
                        self.stats.files_processed += 1
                        self.stats.success_attachments += file_stats["success"]
                        self.stats.error_attachments += file_stats["error"]
                        self.stats.skipped_attachments += file_stats["skipped"]
                        self.stats.total_attachments += file_stats["total"]

                    except Exception as e:
                        logger.error(f"Error processing {md_file.md_path}: {e}")
                        self.stats.files_errored += 1

                    finally:
                        pbar.update(1)

            return self.stats.get_statistics()

        except Exception as e:
            self.logger.error(f"Error during processing: {e}")
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
        """Format statistics for display.

        Returns:
            Formatted statistics string
        """
        stats = self.stats.get_statistics()
        total_files = stats["files_processed"] + stats["files_errored"] + stats["files_skipped"] + stats["files_unchanged"]

        return f"""
╭───────────────────────────────────────── Processing Complete ─────────────────────────────────────────╮
│             Processing Summary                               │
│ ┏━━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━━┳━━━━━━━┳━━━━━━━━━┓      │
│ ┃ Category    ┃ Total ┃ Success ┃ Error ┃ Skipped ┃      │
│ ┡━━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━━╇━━━━━━━╇━━━━━━━━━┩      │
│ │ Files       │ {total_files:5} │ {stats["files_processed"]:7} │ {stats["files_errored"]:5} │ {stats["files_unchanged"]:7} │      │
│ │ Attachments │ {stats["total"]:5} │ {stats["success"]:7} │ {stats["error"]:5} │ {stats["skipped"]:7} │      │
│ └─────────────┴───────┴─────────┴───────┴─────────┘      │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────╯
"""

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
