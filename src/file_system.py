"""File system operations for markdown processing."""

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Generator, List, Optional, Union
import urllib.parse

logger = logging.getLogger(__name__)


@dataclass
class MarkdownFile:
    """Represents a markdown file and its attachments."""

    md_path: Path
    attachment_dir: Optional[Path] = None

    def get_attachment(self, ref_path: Union[str, Path]) -> Optional[Path]:
        """Get the path to an attachment file.

        Args:
            ref_path: The reference path from the markdown file.

        Returns:
            The absolute path to the attachment file, or None if not found.
        """
        # URL decode the reference path
        if isinstance(ref_path, str):
            ref_path = urllib.parse.unquote(ref_path)
        ref_path = Path(ref_path)

        # Bear's export format uses paths relative to the markdown file
        primary_path = self.md_path.parent / ref_path
        if primary_path.exists():
            logger.debug("Found attachment at primary path: %s", primary_path)
            return primary_path

        # Fallback paths if the primary path doesn't exist
        fallback_paths = []
        if self.attachment_dir:
            fallback_paths.extend(
                [
                    self.attachment_dir / ref_path,  # Full path in attachment dir
                    self.attachment_dir
                    / ref_path.name,  # Just the filename in attachment dir
                ]
            )

        for path in fallback_paths:
            try:
                if path.exists():
                    logger.debug("Found attachment at fallback path: %s", path)
                    return path
            except Exception as e:
                logger.debug("Error checking path %s: %s", path, e)
                continue

        logger.debug("Could not find attachment: %s", ref_path)
        return None


class FileSystem:
    """Handles file system operations for markdown processing."""

    def __init__(
        self, src_dir: str | Path, dest_dir: str | Path, cbm_dir: str | Path
    ) -> None:
        """Initialize with source, destination, and system directories.

        Args:
            src_dir: Source directory for markdown files
            dest_dir: Destination directory for processed files
            cbm_dir: Directory for system files and processing
        """
        self.src_dir = Path(src_dir).expanduser().resolve()
        self.dest_dir = Path(dest_dir).expanduser().resolve()
        self.cbm_dir = Path(cbm_dir).expanduser().resolve()

        # Create directories if they don't exist
        self.src_dir.mkdir(parents=True, exist_ok=True)
        self.dest_dir.mkdir(parents=True, exist_ok=True)
        self.cbm_dir.mkdir(parents=True, exist_ok=True)

        logger.debug(
            f"Initialized FileSystem with src_dir={self.src_dir}, "
            f"dest_dir={self.dest_dir}, cbm_dir={self.cbm_dir}"
        )

    def normalize_path(
        self,
        path: Union[str, Path],
        test_root: Optional[Path] = None,
    ) -> Path:
        """Normalize a path, handling cloud storage paths.

        Args:
            path: The path to normalize
            test_root: Optional root for testing cloud storage paths

        Returns:
            Path object with cloud paths mapped to local paths
        """
        # Convert to string first to check for cloud paths
        path_str = str(path)
        logger.debug(f"Normalizing cloud path: {path_str}")

        # Handle iCloud Drive paths
        if "iCloud Drive" in path_str:
            # Try test directory first if provided
            if test_root:
                cloud_base = test_root / "Library/Mobile Documents/com~apple~CloudDocs"
                if cloud_base.exists():
                    logger.debug(f"Using test iCloud base: {cloud_base}")
                    relative_path = path_str.split("iCloud Drive/")[-1]
                    path_obj = cloud_base / relative_path
                    logger.debug(f"Normalized test iCloud path: {path_obj}")
                    return path_obj.resolve()

            # Fall back to user's home directory
            cloud_base = Path.home() / "Library/Mobile Documents/com~apple~CloudDocs"
            logger.debug(f"Found iCloud path, using base: {cloud_base}")
            if not cloud_base.exists():
                logger.warning(f"iCloud base directory not found: {cloud_base}")
                return Path(path).expanduser().resolve()
            relative_path = path_str.split("iCloud Drive/")[-1]
            path_obj = cloud_base / relative_path
            logger.debug(f"Normalized iCloud path: {path_obj}")
            return path_obj.resolve()

        # Handle Google Drive paths
        elif "Google Drive" in path_str:
            # Try test directory first if provided
            if test_root:
                cloud_base = test_root / "Library/CloudStorage"
                if cloud_base.exists():
                    logger.debug(f"Using test Google Drive base: {cloud_base}")
                    for drive_dir in cloud_base.glob("GoogleDrive-*"):
                        if drive_dir.is_dir():
                            relative_path = path_str.split("Google Drive/")[-1]
                            path_obj = drive_dir / "My Drive" / relative_path
                            logger.debug(
                                f"Normalized test Google Drive path: {path_obj}"
                            )
                            return path_obj.resolve()

            # Fall back to user's home directory
            cloud_base = Path.home() / "Library/CloudStorage"
            logger.debug(f"Found Google Drive path, searching in: {cloud_base}")
            if not cloud_base.exists():
                logger.warning(f"Google Drive base directory not found: {cloud_base}")
                return Path(path).expanduser().resolve()
            # Find the Google Drive directory
            for entry in cloud_base.iterdir():
                if entry.name.startswith("GoogleDrive-"):
                    cloud_base = entry / "My Drive"
                    break
            relative_path = path_str.split("Google Drive/")[-1]
            path_obj = cloud_base / relative_path
            logger.debug(f"Normalized Google Drive path: {path_obj}")
            return path_obj.resolve()

        # Regular path
        path_obj = Path(path).expanduser()
        resolved = path_obj.resolve()
        logger.debug(f"Regular path normalized: {resolved}")
        return resolved

    def discover_markdown_files(
        self, start_dir: Optional[Path] = None
    ) -> Generator[MarkdownFile, None, None]:
        """Find all markdown files in source directory.

        Args:
            start_dir: Optional starting directory, defaults to source directory

        Returns:
            Generator yielding MarkdownFile objects
        """
        search_dir = start_dir or self.src_dir
        if not search_dir.exists():
            raise FileNotFoundError(f"Directory not found: {search_dir}")

        for file_path in search_dir.rglob("*.md"):
            if not any(
                p.startswith(".") for p in file_path.parts
            ):  # Skip hidden directories
                attachment_dir = file_path.parent / file_path.stem
                yield MarkdownFile(
                    md_path=file_path,
                    attachment_dir=attachment_dir if attachment_dir.exists() else None,
                )

    def get_attachments(self, attachment_dir: Path) -> List[Path]:
        """Get list of attachment files from directory.

        Args:
            attachment_dir: Directory containing attachments

        Returns:
            Sorted list of attachment file paths
        """
        if not attachment_dir.exists():
            return []

        attachments = []
        for file_path in attachment_dir.iterdir():
            if not file_path.name.startswith("."):  # Skip hidden files
                attachments.append(file_path)

        # Sort by name to ensure consistent order
        return sorted(attachments, key=lambda p: p.name)

    def ensure_output_dir(self, src_file: Path) -> Path:
        """Create output directory structure and return output path."""
        rel_path = src_file.relative_to(self.src_dir)
        output_path = self.dest_dir / rel_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        return output_path
