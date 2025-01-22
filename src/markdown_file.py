from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional
import urllib.parse


@dataclass
class MarkdownFile:
    """A markdown file with its attachments."""

    md_path: Path
    attachment_dir: Optional[Path] = None
    _attachments: List[Path] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        """Initialize the markdown file.

        Checks that the markdown file exists and scans for attachments
        if an attachment directory is provided.
        """
        if not self.md_path.exists():
            raise FileNotFoundError(f"Markdown file not found: {self.md_path}")

        if self.attachment_dir and self.attachment_dir.exists():
            # Get all files in the attachment directory, excluding hidden files
            self._attachments = [
                path
                for path in self.attachment_dir.iterdir()
                if not path.name.startswith(".") and path.is_file()
            ]
            self._attachments.sort()  # Sort for consistent ordering

    @property
    def attachments(self) -> List[Path]:
        """Get the list of attachments."""
        return self._attachments

    def get_attachment(self, ref_path: str) -> Optional[Path]:
        """Get an attachment by its reference path.

        Args:
            ref_path: The reference path from the markdown file (URL encoded)

        Returns:
            The attachment path if found, None otherwise
        """
        if not self.attachment_dir:
            return None

        # URL decode the reference path
        decoded_path = urllib.parse.unquote(ref_path)
        ref = Path(decoded_path)

        # First try exact path match relative to attachment_dir
        full_path = self.attachment_dir / ref.name
        if full_path.exists() and full_path in self._attachments:
            return full_path

        # Then try to find by filename only
        for attachment in self._attachments:
            if attachment.name == ref.name:
                return attachment

        return None
