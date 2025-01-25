"""File system operations for markdown processing."""

from dataclasses import dataclass, field
import logging
from pathlib import Path
from typing import Generator, List, Optional, Union
import urllib.parse
import os

logger = logging.getLogger(__name__)


@dataclass
class MarkdownFile:
    """Represents a markdown file and its attachments."""

    md_path: Path
    attachment_dir: Optional[Path] = None
    _fs: Optional['FileSystem'] = None
    _attachments: List[Path] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        """Initialize the markdown file.

        Checks that the markdown file exists and scans for attachments
        if an attachment directory is provided.
        """
        if not self.md_path.exists():
            raise FileNotFoundError(f"Markdown file not found: {self.md_path}")

        # If no attachment directory was provided, try to find it
        if not self.attachment_dir:
            potential_dir = self.md_path.parent / self.md_path.stem
            if potential_dir.exists() and potential_dir.is_dir():
                self.attachment_dir = potential_dir

        # Scan for attachments if we have a directory
        if self.attachment_dir and self.attachment_dir.exists():
            try:
                # Get all files in the attachment directory, excluding hidden files
                self._attachments = [
                    path
                    for path in self.attachment_dir.iterdir()
                    if not path.name.startswith(".") and path.is_file()
                ]
                self._attachments.sort()  # Sort for consistent ordering
                logger.debug(f"Found {len(self._attachments)} attachments in {self.attachment_dir}")
            except Exception as e:
                logger.error(f"Error scanning attachment directory {self.attachment_dir}: {e}")
                self._attachments = []

    @property
    def attachments(self) -> List[Path]:
        """Get the list of attachments."""
        return self._attachments

    @property
    def content(self) -> str:
        """Get the content of the markdown file."""
        return self.md_path.read_text()

    def get_attachment(self, ref_path: Union[str, Path]) -> Optional[Path]:
        """Get an attachment by its reference path.

        Args:
            ref_path: The reference path from the markdown file (URL encoded)

        Returns:
            The attachment path if found, None otherwise
        """
        if not self.attachment_dir and not self.md_path.parent:
            logger.debug("No attachment directory or parent directory available")
            return None

        # URL decode the reference path and convert to string
        ref_str = urllib.parse.unquote(str(ref_path))
        logger.debug(f"Looking for attachment: {ref_str}")
        logger.debug(f"Markdown file path: {self.md_path}")
        logger.debug(f"Attachment directory: {self.attachment_dir}")

        # Split the path into segments and decode each segment
        path_segments = ref_str.split("/")
        decoded_segments = [urllib.parse.unquote(segment) for segment in path_segments]
        decoded_path = "/".join(decoded_segments)
        logger.debug(f"Decoded path: {decoded_path}")

        # If we have a FileSystem instance, try cloud path resolution first
        if self._fs:
            # Try the full path relative to the markdown file's directory
            full_path = self.md_path.parent / decoded_path
            logger.debug(f"Trying full path: {full_path}")

            # Try to normalize the path
            cloud_path = self._fs.normalize_cloud_path(str(full_path))
            logger.debug(f"Normalized cloud path from full path: {cloud_path}")
            if cloud_path and cloud_path.exists() and cloud_path.is_file():
                logger.debug(f"Found attachment at cloud path: {cloud_path}")
                return cloud_path.resolve()

        # Try to find the file in the markdown file's directory
        filename = os.path.basename(decoded_path)
        parent_path = self.md_path.parent / filename
        logger.debug(f"Trying parent path: {parent_path}")
        if parent_path.exists() and parent_path.is_file():
            logger.debug(f"Found attachment at parent path: {parent_path}")
            return parent_path.resolve()

        # Try to find the file in the attachment directory
        if self.attachment_dir:
            direct_path = self.attachment_dir / filename
            logger.debug(f"Trying direct path: {direct_path}")
            if direct_path.exists() and direct_path.is_file():
                logger.debug(f"Found attachment at direct path: {direct_path}")
                return direct_path.resolve()

        # As a last resort, check if the file exists in the list of known attachments
        logger.debug(f"Checking {len(self._attachments)} known attachments")
        for attachment in self._attachments:
            logger.debug(f"Checking known attachment: {attachment}")
            if attachment.name == filename:
                logger.debug(f"Found attachment in known attachments: {attachment}")
                return attachment

        logger.debug(f"Could not find attachment: {ref_str}")
        return None

    def normalize_cloud_path(self, path: str, test_root: Optional[Path] = None) -> Optional[Path]:
        """Normalize cloud storage paths.

        Args:
            path: Path to normalize
            test_root: Optional root for testing cloud storage paths

        Returns:
            Path object with cloud paths mapped to local paths
        """
        # First decode any URL encoded components
        decoded_path = urllib.parse.unquote(path)
        path_obj = Path(decoded_path).expanduser()
        logger.debug(f"Normalizing path: {path}")
        logger.debug(f"Decoded path: {decoded_path}")
        logger.debug(f"Path object: {path_obj}")

        # Handle iCloud Drive paths
        if "iCloud Drive" in str(path_obj):
            logger.debug("Found iCloud Drive path")
            # Try test directory first if provided
            if test_root:
                cloud_base = test_root / "Library/Mobile Documents/com~apple~CloudDocs"
                if cloud_base.exists():
                    logger.debug(f"Using test iCloud base: {cloud_base}")
                    relative_path = str(path_obj).split("iCloud Drive/")[-1]
                    path_obj = cloud_base / relative_path
                    logger.debug(f"Normalized test iCloud path: {path_obj}")
                    return path_obj.resolve()

            # Fall back to user's home directory
            cloud_base = Path.home() / "Library/Mobile Documents/com~apple~CloudDocs"
            logger.debug(f"Found iCloud path, using base: {cloud_base}")
            if not cloud_base.exists():
                logger.warning(f"iCloud base directory not found: {cloud_base}")
                return None
            relative_path = str(path_obj).split("iCloud Drive/")[-1]
            path_obj = cloud_base / relative_path
            logger.debug(f"Normalized iCloud path: {path_obj}")
            return path_obj.resolve()

        # Handle paths that are already in iCloud format
        if "com~apple~CloudDocs" in str(path_obj):
            logger.debug("Found path already in iCloud format")
            return path_obj

        # Handle Google Drive paths
        if "Google Drive" in str(path_obj):
            logger.debug("Found Google Drive path")
            # Try test directory first if provided
            if test_root:
                cloud_base = test_root / "Library/CloudStorage"
                if cloud_base.exists():
                    logger.debug(f"Using test Google Drive base: {cloud_base}")
                    for drive_dir in cloud_base.glob("GoogleDrive-*"):
                        if drive_dir.is_dir():
                            relative_path = str(path_obj).split("Google Drive/")[-1]
                            path_obj = drive_dir / "My Drive" / relative_path
                            logger.debug(f"Normalized test Google Drive path: {path_obj}")
                            return path_obj.resolve()

            # Fall back to user's home directory
            cloud_base = Path.home() / "Library/CloudStorage"
            logger.debug(f"Found Google Drive path, searching in: {cloud_base}")
            if not cloud_base.exists():
                logger.warning(f"Google Drive base directory not found: {cloud_base}")
                return None
            # Find the Google Drive directory
            for entry in cloud_base.iterdir():
                if entry.name.startswith("GoogleDrive-"):
                    cloud_base = entry / "My Drive"
                    break
            relative_path = str(path_obj).split("Google Drive/")[-1]
            path_obj = cloud_base / relative_path
            logger.debug(f"Normalized Google Drive path: {path_obj}")
            return path_obj.resolve()

        # Regular path
        logger.debug("Treating as regular path")
        path_obj = Path(path).expanduser()
        resolved = path_obj.resolve()
        logger.debug(f"Regular path normalized: {resolved}")
        return resolved


class FileSystem:
    """Handles file system operations for markdown processing."""

    def __init__(
        self, src_dir: str | Path, dest_dir: str | Path, cbm_dir: str | Path
    ) -> None:
        """Initialize with source, destination, and system directories.

        Args:
            src_dir: Source directory containing markdown files
            dest_dir: Destination directory for processed files
            cbm_dir: Directory for system files
        """
        # Convert all paths to Path objects and resolve them
        self.src_dir = Path(src_dir).expanduser()
        self.dest_dir = Path(dest_dir).expanduser()
        self.cbm_dir = Path(cbm_dir).expanduser()

        # Create directories if they don't exist
        self.dest_dir.mkdir(parents=True, exist_ok=True)
        self.cbm_dir.mkdir(parents=True, exist_ok=True)

        # Set up logging
        self.log_dir = self.cbm_dir / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)

        logger.debug(f"Initialized FileSystem with src_dir={self.src_dir}")

    def normalize_cloud_path(self, path: str, test_root: Optional[Path] = None) -> Optional[Path]:
        """Normalize cloud storage paths.

        Args:
            path: Path to normalize
            test_root: Optional root for testing cloud storage paths

        Returns:
            Path object with cloud paths mapped to local paths
        """
        # First decode any URL encoded components
        decoded_path = urllib.parse.unquote(path)
        path_obj = Path(decoded_path).expanduser()
        logger.debug(f"Normalizing path: {path}")
        logger.debug(f"Decoded path: {decoded_path}")
        logger.debug(f"Path object: {path_obj}")

        # Handle iCloud Drive paths
        if "iCloud Drive" in str(path_obj):
            logger.debug("Found iCloud Drive path")
            # Try test directory first if provided
            if test_root:
                cloud_base = test_root / "Library/Mobile Documents/com~apple~CloudDocs"
                if cloud_base.exists():
                    logger.debug(f"Using test iCloud base: {cloud_base}")
                    relative_path = str(path_obj).split("iCloud Drive/")[-1]
                    path_obj = cloud_base / relative_path
                    logger.debug(f"Normalized test iCloud path: {path_obj}")
                    return path_obj.resolve()

            # Fall back to user's home directory
            cloud_base = Path.home() / "Library/Mobile Documents/com~apple~CloudDocs"
            logger.debug(f"Found iCloud path, using base: {cloud_base}")
            if not cloud_base.exists():
                logger.warning(f"iCloud base directory not found: {cloud_base}")
                return None
            relative_path = str(path_obj).split("iCloud Drive/")[-1]
            path_obj = cloud_base / relative_path
            logger.debug(f"Normalized iCloud path: {path_obj}")
            return path_obj.resolve()

        # Handle paths that are already in iCloud format
        if "com~apple~CloudDocs" in str(path_obj):
            logger.debug("Found path already in iCloud format")
            return path_obj

        # Handle Google Drive paths
        if "Google Drive" in str(path_obj):
            logger.debug("Found Google Drive path")
            # Try test directory first if provided
            if test_root:
                cloud_base = test_root / "Library/CloudStorage"
                if cloud_base.exists():
                    logger.debug(f"Using test Google Drive base: {cloud_base}")
                    for drive_dir in cloud_base.glob("GoogleDrive-*"):
                        if drive_dir.is_dir():
                            relative_path = str(path_obj).split("Google Drive/")[-1]
                            path_obj = drive_dir / "My Drive" / relative_path
                            logger.debug(f"Normalized test Google Drive path: {path_obj}")
                            return path_obj.resolve()

            # Fall back to user's home directory
            cloud_base = Path.home() / "Library/CloudStorage"
            logger.debug(f"Found Google Drive path, searching in: {cloud_base}")
            if not cloud_base.exists():
                logger.warning(f"Google Drive base directory not found: {cloud_base}")
                return None
            # Find the Google Drive directory
            for entry in cloud_base.iterdir():
                if entry.name.startswith("GoogleDrive-"):
                    cloud_base = entry / "My Drive"
                    break
            relative_path = str(path_obj).split("Google Drive/")[-1]
            path_obj = cloud_base / relative_path
            logger.debug(f"Normalized Google Drive path: {path_obj}")
            return path_obj.resolve()

        # Regular path
        logger.debug("Treating as regular path")
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

        Raises:
            FileNotFoundError: If the start directory does not exist
        """
        start_dir = start_dir or self.src_dir
        logger.debug(f"Discovering markdown files in: {start_dir}")

        # Check if directory exists
        if not start_dir.exists():
            raise FileNotFoundError(f"Directory not found: {start_dir}")

        try:
            # Get all markdown files in the directory
            for md_path in start_dir.glob("**/*.md"):
                try:
                    # Skip hidden files and directories
                    if any(part.startswith(".") for part in md_path.parts):
                        continue

                    # Get potential attachment directory (same name as markdown file without extension)
                    attachment_dir = md_path.parent / md_path.stem

                    # Try to normalize the attachment directory path if it's a cloud path
                    normalized_attachment_dir = self.normalize_cloud_path(str(attachment_dir))
                    if normalized_attachment_dir:
                        attachment_dir = normalized_attachment_dir

                    # Check if attachment directory exists
                    has_attachments = attachment_dir.exists() and attachment_dir.is_dir()
                    logger.debug(f"Checking attachment directory: {attachment_dir} (exists: {has_attachments})")

                    # Create MarkdownFile object
                    md_file = MarkdownFile(
                        md_path=md_path,
                        attachment_dir=attachment_dir if has_attachments else None,
                        _fs=self
                    )

                    logger.debug(
                        f"Found markdown file: {md_path} "
                        f"(has attachments: {has_attachments})"
                    )

                    yield md_file

                except Exception as e:
                    logger.error(f"Error processing markdown file {md_path}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error discovering markdown files: {e}")
            raise

    def get_attachments(self, attachment_dir: Path) -> List[Path]:
        """Get all attachments in a directory.

        Args:
            attachment_dir: Directory containing attachments

        Returns:
            List of attachment paths
        """
        if not attachment_dir.exists():
            logger.debug(f"Attachment directory does not exist: {attachment_dir}")
            return []

        try:
            # Get all files in the directory, excluding hidden files
            attachments = []
            for path in attachment_dir.iterdir():
                if not path.name.startswith(".") and path.is_file():
                    try:
                        # Try to resolve the path to handle any symlinks or special paths
                        resolved = path.resolve()
                        logger.debug(f"Found attachment: {resolved}")
                        attachments.append(resolved)
                    except Exception as e:
                        logger.error(f"Error resolving attachment path {path}: {e}")
                        continue

            # Sort for consistent ordering
            attachments.sort()
            return attachments

        except Exception as e:
            logger.error(f"Error getting attachments from {attachment_dir}: {e}")
            return []

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

    def ensure_output_dir(self, src_file: Path) -> Path:
        """Create output directory structure and return output path.

        Args:
            src_file: Source file path

        Returns:
            Output file path
        """
        # Get relative path from source directory
        try:
            rel_path = src_file.relative_to(self.src_dir)
        except ValueError:
            # If not relative to source directory, just use the filename
            rel_path = Path(src_file.name)

        # Create output path
        out_path = self.dest_dir / rel_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        return out_path
