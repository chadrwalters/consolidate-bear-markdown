"""Test configuration and fixtures."""

import os
import shutil
from pathlib import Path
import pytest


@pytest.fixture
def clean_tmp_path(tmp_path):
    """Create a clean temporary directory that won't be affected by Nova."""
    # Create a .nobackup file to prevent Nova from creating .nova directories
    (tmp_path / ".nobackup").touch()
    yield tmp_path
    # Clean up
    if tmp_path.exists():
        shutil.rmtree(tmp_path, ignore_errors=True)
