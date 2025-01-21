"""File management and path handling for markdown processing."""

import logging
import os
import urllib.parse
import weakref
import atexit
import shutil
from pathlib import Path
from typing import Dict, Optional, Set
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class FileResource:
    """Represents a tracked file resource."""

    path: Path
    reference_count: int = 0
    dependent_files: Set[Path] = field(default_factory=set)
    is_temporary: bool = False


class FileManager:
    """Manages file resources, paths, and dependencies."""

    def __init__(self, cbm_dir: Path, src_dir: Path, dest_dir: Path):
        """Initialize the file manager.

        Args:
            cbm_dir: Directory for system files
            src_dir: Source directory for markdown files
            dest_dir: Destination directory for processed files
        """
        self.cbm_dir = Path(cbm_dir)
        self.src_dir = Path(src_dir)
        self.dest_dir = Path(dest_dir)

        # Create system directories
        self.images_dir = self.cbm_dir / "images"
        self.temp_dir = self.cbm_dir / "temp"
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        # Resource tracking
        self.resources: Dict[str, FileResource] = {}
        self._finalizer = weakref.finalize(self, self._cleanup)
        atexit.register(self.cleanup)

    def get_stable_path(self, file_path: Path, subdir: str = "images") -> Path:
        """Get a stable path for a file in a subdirectory of .cbm.

        Args:
            file_path: Original file path
            subdir: Subdirectory within .cbm to store the file

        Returns:
            A stable path in the specified subdirectory
        """
        target_dir = self.cbm_dir / subdir
        target_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Create a stable name based on the directory structure
            rel_path = file_path.resolve().relative_to(self.src_dir.resolve())
            stable_name = str(rel_path).replace('/', '_')
        except ValueError:
            # If not relative to src_dir, just use the filename
            stable_name = file_path.name

        return target_dir / stable_name

    def track_file(self, file_path: Path, dependent_file: Optional[Path] = None, *, is_temporary: bool = False) -> None:
        """Track a file resource.

        Args:
            file_path: Path to the file to track
            dependent_file: Path to the file that depends on this resource
            is_temporary: Whether this is a temporary file that should be cleaned up
        """
        path_str = str(file_path)
        if path_str not in self.resources:
            self.resources[path_str] = FileResource(path=file_path, is_temporary=is_temporary)

        resource = self.resources[path_str]
        resource.reference_count += 1
        if dependent_file:
            resource.dependent_files.add(dependent_file)
        logger.debug(f"Tracking {file_path} (count={resource.reference_count}, temporary={is_temporary})")

    def release_file(self, file_path: Path, dependent_file: Optional[Path] = None) -> None:
        """Release a file resource.

        Args:
            file_path: Path to the file to release
            dependent_file: Path to the file that no longer depends on this resource
        """
        path_str = str(file_path)
        if path_str not in self.resources:
            logger.warning(f"Attempted to release untracked file: {file_path}")
            return

        resource = self.resources[path_str]
        resource.reference_count -= 1
        if dependent_file:
            resource.dependent_files.discard(dependent_file)

        if resource.reference_count <= 0 and not resource.dependent_files:
            if resource.is_temporary and file_path.exists():
                try:
                    file_path.unlink()
                    logger.debug(f"Deleted temporary file: {file_path}")
                except Exception as e:
                    logger.warning(f"Failed to delete temporary file {file_path}: {e}")
            del self.resources[path_str]
            logger.debug(f"Released {file_path}")

    def normalize_path(self, path: Path | str) -> Path:
        """Normalize a path, handling URL encoding and special characters.

        Args:
            path: Path to normalize

        Returns:
            Normalized path
        """
        if isinstance(path, str):
            # Handle URL-encoded paths
            path = urllib.parse.unquote(path)
            path = Path(path)

        try:
            # Resolve the path if it exists
            if path.exists():
                return path.resolve()

            # For non-existent paths, normalize the parts
            parts = []
            for part in path.parts:
                # Handle URL-encoded parts
                decoded = urllib.parse.unquote(part)
                # Remove any problematic characters
                cleaned = "".join(c for c in decoded if c.isprintable() and c not in '<>:"|?*')
                parts.append(cleaned)

            return Path(*parts)

        except Exception as e:
            logger.warning(f"Error normalizing path {path}: {str(e)}")
            return path

    def translate_path(self, path: Path) -> Path:
        """Translate a path for output.

        Args:
            path: Path to translate.

        Returns:
            Translated path.
        """
        try:
            # If path is in .cbm directory, make it relative to .cbm
            if str(path).startswith(str(self.cbm_dir)):
                return Path("../cbm") / path.relative_to(self.cbm_dir)
            return path
        except ValueError:
            logger.warning(f"Path is outside allowed directories: {path}")
            return path

    def validate_path(self, path: Path | str) -> bool:
        """Validate a path for security and accessibility.

        Args:
            path: Path to validate

        Returns:
            True if the path is valid, False otherwise
        """
        try:
            path = self.normalize_path(path)

            # Check if path exists
            if not path.exists():
                logger.warning(f"Path does not exist: {path}")
                return False

            # Check if path is accessible
            try:
                path.stat()
            except (PermissionError, OSError):
                logger.warning(f"Path is not accessible: {path}")
                return False

            # Check if path is within allowed directories
            allowed_dirs = [self.src_dir, self.dest_dir, self.cbm_dir]
            if not any(self._is_relative_to(path, allowed_dir) for allowed_dir in allowed_dirs):
                logger.warning(f"Path is outside allowed directories: {path}")
                return False

            return True

        except Exception as e:
            logger.error(f"Error validating path {path}: {str(e)}")
            return False

    def _is_relative_to(self, path: Path, base: Path) -> bool:
        """Check if a path is relative to a base directory.

        Args:
            path: Path to check
            base: Base directory

        Returns:
            True if path is relative to base, False otherwise
        """
        try:
            path.relative_to(base)
            return True
        except ValueError:
            return False

    def _cleanup_resource(self, resource: FileResource) -> None:
        """Clean up a single resource.

        Args:
            resource: The resource to clean up
        """
        try:
            if resource.is_temporary and resource.path.exists():
                resource.path.unlink()
                logger.debug(f"Cleaned up resource: {resource.path.name}")
        except Exception as e:
            logger.error(f"Error cleaning up resource {resource.path.name}: {str(e)}")

        # Remove from tracking
        self.resources.pop(str(resource.path), None)

    def cleanup(self) -> None:
        """Clean up all resources."""
        # Clean up tracked resources
        for path_str, resource in list(self.resources.items()):
            if resource.is_temporary and Path(path_str).exists():
                try:
                    Path(path_str).unlink()
                    logger.debug(f"Cleaned up temporary file: {path_str}")
                except Exception as e:
                    logger.warning(f"Failed to clean up temporary file {path_str}: {e}")
        self.resources.clear()

        # Clean up temp directory
        if self.temp_dir.exists():
            try:
                shutil.rmtree(self.temp_dir)
                logger.debug("Cleaned up temp directory")
            except Exception as e:
                logger.warning(f"Error cleaning up temp directory: {e}")

        logger.debug("Cleaned up all resources")

    def _cleanup(self) -> None:
        """Internal cleanup method called by weakref finalizer."""
        try:
            self.cleanup()
        except Exception:
            pass  # Suppress errors during finalizer cleanup

    def __del__(self) -> None:
        """Cleanup resources when the object is deleted."""
        try:
            self.cleanup()
        except Exception:
            pass  # Suppress errors during deletion
