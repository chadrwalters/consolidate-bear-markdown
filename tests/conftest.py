"""Test configuration and fixtures."""

import os
from pathlib import Path
import shutil
import time
from typing import Any, Generator

import pytest


@pytest.fixture
def clean_tmp_path(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a clean temporary directory that won't be affected by Nova.

    Args:
        tmp_path: Pytest's temporary directory fixture

    Returns:
        Generator yielding path to clean temporary directory
    """
    # Create a subdirectory to avoid Nova's .nova directory
    test_dir = tmp_path / "test"
    test_dir.mkdir(parents=True, exist_ok=True)

    yield test_dir

    # Clean up
    if test_dir.exists():
        shutil.rmtree(test_dir)


@pytest.hookimpl
def pytest_sessionfinish(session: Any, exitstatus: int) -> None:
    """Called after the entire test run finishes but before pytest's cleanup.

    This hook removes all .nova directories from the test temp area to prevent
    pytest from encountering non-empty directory errors during its cleanup.

    Args:
        session: The pytest session object
        exitstatus: The status code from the test run
    """
    base_temp = session.config._tmp_path_factory.getbasetemp()
    if not base_temp:
        return

    # Try cleanup multiple times with delays to handle locked files
    max_retries = 3
    for attempt in range(max_retries):
        remaining_dirs = []
        for root, dirs, _files in os.walk(str(base_temp), topdown=False):
            for d in dirs:
                if d == ".nova":
                    nova_dir = os.path.join(root, d)
                    try:
                        shutil.rmtree(nova_dir)
                    except OSError:
                        remaining_dirs.append(nova_dir)

        if not remaining_dirs:
            break

        # Wait before retrying
        if attempt < max_retries - 1:
            time.sleep(0.1 * (attempt + 1))
