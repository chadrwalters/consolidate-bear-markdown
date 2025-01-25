"""Progress tracking management for file and attachment processing."""
from typing import Optional, Any
from tqdm import tqdm

class ProgressManager:
    """Manages progress bars for file and attachment processing."""

    def __init__(self) -> None:
        """Initialize progress bars as None."""
        self.file_bar: Optional[tqdm] = None
        self.attach_bar: Optional[tqdm] = None

    def __enter__(self) -> 'ProgressManager':
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Optional[type], exc_val: Optional[Exception], exc_tb: Optional[Any]) -> None:
        """Clean up progress bars on exit."""
        if self.file_bar:
            self.file_bar.close()
        if self.attach_bar:
            self.attach_bar.close()

    def start_file_progress(self, total_files: int) -> None:
        """Initialize the file progress bar.

        Args:
            total_files: Total number of markdown files to process.
        """
        self.file_bar = tqdm(
            total=total_files,
            desc="Processing Markdown Files",
            unit="files"
        )

    def start_attachment_progress(self, total_attachments: int) -> None:
        """Initialize the attachment progress bar.

        Args:
            total_attachments: Total number of attachments in current file.
        """
        if self.attach_bar:
            self.attach_bar.close()

        self.attach_bar = tqdm(
            total=total_attachments,
            desc="Processing Attachments",
            unit="att",
            leave=False  # Don't leave this bar when done
        )

    def update_file_progress(self, amount: int = 1) -> None:
        """Update the file progress bar.

        Args:
            amount: Amount to increment by (default: 1)
        """
        if self.file_bar:
            self.file_bar.update(amount)

    def update_attachment_progress(self, amount: int = 1) -> None:
        """Update the attachment progress bar.

        Args:
            amount: Amount to increment by (default: 1)
        """
        if self.attach_bar:
            self.attach_bar.update(amount)

    def write_message(self, message: str) -> None:
        """Write a message to the console without disrupting progress bars.

        Args:
            message: Message to display
        """
        tqdm.write(message)
