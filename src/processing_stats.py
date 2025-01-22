"""Module for tracking processing statistics."""

from typing import List


class ProcessingStats:
    """Class for tracking processing statistics."""

    def __init__(self) -> None:
        """Initialize processing statistics."""
        self.files_processed = 0
        self.files_errored = 0
        self.files_skipped = 0
        self.files_unchanged = 0
        self.total_attachments = 0
        self.success_attachments = 0
        self.error_attachments = 0
        self.skipped_attachments = 0
        self.errors: List[str] = []

    def record_success(self, file_path: str) -> None:
        """Record a successful attachment conversion.

        Args:
            file_path: Path to the successfully processed file
        """
        self.success_attachments += 1
        self.total_attachments += 1

    def record_error(self, file_path: str, error_msg: str) -> None:
        """Record an error during processing.

        Args:
            file_path: Path to the file that had an error
            error_msg: Description of the error
        """
        self.error_attachments += 1
        self.total_attachments += 1
        self.errors.append(f"{file_path}: {error_msg}")

    def record_skipped(self, file_path: str) -> None:
        """Record a skipped attachment.

        Args:
            file_path: Path to the skipped file
        """
        self.skipped_attachments += 1
        self.total_attachments += 1

    def record_unchanged(self, file_path: str) -> None:
        """Record a file that was skipped due to no changes.

        Args:
            file_path: Path to the unchanged file
        """
        self.files_unchanged += 1

    def update_file_stats(self, total: int, success: int, error: int, skipped: int) -> None:
        """Update file-level statistics.

        Args:
            total: Total number of attachments in file
            success: Number of successful conversions
            error: Number of failed conversions
            skipped: Number of skipped attachments
        """
        self.files_processed += 1
        self.total_attachments += total
        self.skipped_attachments += skipped

        # A file is successful if it has no errors, regardless of attachments
        if error > 0:
            self.files_errored += 1
        else:
            self.success_attachments += 1

    def get_statistics(self) -> dict[str, int]:
        """Get the current statistics.

        Returns:
            Dictionary containing the current statistics
        """
        return {
            # File-level statistics
            "files_processed": self.files_processed,
            "files_errored": self.files_errored,
            "files_skipped": self.files_skipped,
            "files_unchanged": self.files_unchanged,
            # Attachment-level statistics
            "success": self.success_attachments,
            "error": self.error_attachments,
            "missing": self.files_skipped,
            "skipped": self.skipped_attachments,
            "total": self.total_attachments,
        }

    def get_error_summary(self) -> str:
        """Get error type summary.

        Returns:
            Formatted error summary string
        """
        if not self.errors:
            return "No errors occurred."

        summary = ["Error type breakdown:"]
        for error in self.errors:
            summary.append(f"  - {error}")
        return "\n".join(summary)

    def _format_summary(self) -> str:
        """Format a summary of the statistics.

        Returns:
            Formatted summary string
        """
        total_files = self.files_processed + self.files_errored + self.files_skipped + self.files_unchanged
        return f"""
Processing Summary:

Files:
- Total: {total_files}
- Processed: {self.files_processed}
- Errors: {self.files_errored}
- Skipped (Processing): {self.files_skipped}
- Skipped (Unchanged): {self.files_unchanged}

Attachments:
- Total: {self.total_attachments}
- Processed: {self.success_attachments}
- Errors: {self.error_attachments}
- Skipped: {self.skipped_attachments}
"""
