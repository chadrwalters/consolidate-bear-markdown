"""Module for tracking processing statistics."""

from typing import List, Dict, Tuple, Optional, Set
from dataclasses import dataclass, field
from enum import Enum, auto


class ErrorType(Enum):
    """Error types for processing."""
    NO_ATTACHMENTS = auto()
    EXTERNAL_URL = auto()
    FILE_NOT_FOUND = auto()
    PROCESSING_ERROR = auto()
    UNSUPPORTED_TYPE = auto()
    GENERAL = auto()


@dataclass
class ProcessingStats:
    """Class to track processing statistics."""

    def __init__(self) -> None:
        """Initialize processing statistics."""
        self.total_files = 0
        self.files_processed = 0
        self.files_skipped = 0
        self.files_unchanged = 0
        self.files_with_errors = 0
        self.total_attachments = 0
        self.successful_attachments = 0
        self.skipped_attachments = 0
        self.external_urls = 0
        self.images_skipped = 0
        self.error_types: Dict[ErrorType, int] = {}
        self.skipped_files: Set[str] = set()
        self.processed_files: Set[str] = set()
        self.error_files: Set[str] = set()
        self.unchanged_files: Set[str] = set()
        self.file_errors: Dict[str, str] = {}  # file_path -> error_message
        self.attachment_errors: Dict[str, Tuple[str, ErrorType]] = {}  # file_path -> (error_message, error_type)

    def record_total(self, total: int) -> None:
        """Record total number of files found."""
        self.total_files = total

    def record_processed(self, file_path: str) -> None:
        """Record a file as processed."""
        if file_path not in self.processed_files:
            self.processed_files.add(file_path)
            self.files_processed += 1

    def record_skipped(self, file_path: str) -> None:
        """Record a file as skipped."""
        if file_path not in self.skipped_files:
            self.skipped_files.add(file_path)
            self.files_skipped += 1

    def record_unchanged(self, file_path: str) -> None:
        """Record a file as unchanged."""
        if file_path not in self.unchanged_files:
            self.unchanged_files.add(file_path)
            self.files_unchanged += 1

    def record_error(self, file_path: str, error: str) -> None:
        """Record a file as having an error."""
        if file_path not in self.error_files:
            self.error_files.add(file_path)
            self.files_with_errors += 1
            self.file_errors[file_path] = error

    def record_attachment_success(self) -> None:
        """Record a successful attachment processing."""
        self.total_attachments += 1
        self.successful_attachments += 1

    def record_attachment_error(self, error_type: Optional[ErrorType] = None, file_path: Optional[str] = None, error_msg: Optional[str] = None) -> None:
        """Record an attachment processing error."""
        self.total_attachments += 1
        if error_type:
            self.error_types[error_type] = self.error_types.get(error_type, 0) + 1
        if file_path and error_msg:
            self.attachment_errors[file_path] = (error_msg, error_type or ErrorType.GENERAL)

    def record_attachment_skipped(self, error_type: Optional[ErrorType] = None) -> None:
        """Record a skipped attachment."""
        self.total_attachments += 1
        self.skipped_attachments += 1
        if error_type:
            self.error_types[error_type] = self.error_types.get(error_type, 0) + 1

    def record_external_url(self) -> None:
        """Record an external URL."""
        self.external_urls += 1
        # Don't increment total_attachments or skipped_attachments for external URLs

    def record_image_skipped(self) -> None:
        """Record an image that was skipped due to --no_image flag."""
        self.images_skipped += 1
        self.total_attachments += 1
        self.skipped_attachments += 1

    def _format_summary(self) -> str:
        """Format the processing summary."""
        summary = ""
        summary += "─" * 53 + "\n"
        summary += " " * 16 + "Processing Summary\n"
        summary += "─" * 20 + "┬" + "─" * 32 + "\n"
        summary += " Files              │ Attachments\n"
        summary += "─" * 20 + "┼" + "─" * 32 + "\n"
        summary += f" Total: {self.total_files:<11} │ Total: {self.total_attachments}\n"
        summary += f" Processed: {self.files_processed:<7} │ Processed: {self.successful_attachments}\n"
        summary += f" Errors: {self.files_with_errors:<10} │ Errors: {sum(self.error_types.values())}\n"
        summary += f" Skipped: {self.files_skipped:<9} │ Skipped: {self.skipped_attachments}\n"
        summary += f" Unchanged: {self.files_unchanged:<8} │ External URLs: {self.external_urls}\n"
        if self.images_skipped > 0:
            summary += f" Images Skipped: {self.images_skipped:<5} │ (--no_image flag)\n"
        summary += "─" * 53 + "\n"

        if self.file_errors:
            summary += "\nFile Errors:\n"
            for file_path, error in self.file_errors.items():
                summary += f"  {file_path}: {error}\n"

        if self.attachment_errors:
            summary += "\nAttachment Errors:\n"
            for file_path, (error_msg, error_type) in self.attachment_errors.items():
                summary += f"  {file_path}: {error_type.name} - {error_msg}\n"

        if self.error_types:
            summary += "\nError Types:\n"
            for error_type, count in self.error_types.items():
                summary += f"  {error_type.name}: {count}\n"

        return summary

    def __str__(self) -> str:
        """Return string representation of stats."""
        return self._format_summary()

    def get_statistics(self) -> dict:
        """Get all statistics as a dictionary.

        Returns:
            Dictionary containing all statistics
        """
        return {
            "total_files": self.total_files,
            "files_processed": self.files_processed,
            "files_skipped": self.files_skipped,
            "files_unchanged": self.files_unchanged,
            "files_errored": self.files_with_errors,
            "total_attachments": self.total_attachments,
            "success_attachments": self.successful_attachments,
            "skipped_attachments": self.skipped_attachments,
            "error_attachments": len(self.error_types),
            "external_urls": self.external_urls,
            "images_skipped": self.images_skipped
        }
