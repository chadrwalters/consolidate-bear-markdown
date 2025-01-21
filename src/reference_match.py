"""Reference matching and parsing for markdown content."""

import re
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

@dataclass
class ReferenceMatch:
    """Represents a reference match in markdown content."""
    original_text: str
    alt_text: str
    link_path: str
    embed: bool
    is_image: bool
    metadata: dict

def find_markdown_references(content: str) -> List[ReferenceMatch]:
    """Find all references in markdown content.

    This unified function finds both image and link references, along with any
    embedded metadata in HTML comments.

    Args:
        content: The markdown content to search

    Returns:
        List of ReferenceMatch objects
    """
    # Match links/images followed by optional HTML comments containing metadata
    pattern = r'(?:!\[(.*?)\]|\[(.*?)\])\((.*?)\)(?:<!--\s*(.*?)\s*-->)?'
    references = []

    for match in re.finditer(pattern, content):
        # Group 1 is image alt text, Group 2 is link alt text
        is_image = match.group(1) is not None
        alt_text = match.group(1) or match.group(2) or ""
        link_path = match.group(3)
        metadata_str = match.group(4)

        # Parse metadata if present
        metadata = {}
        if metadata_str:
            try:
                metadata = json.loads(metadata_str)
            except json.JSONDecodeError:
                logger.warning(f"Invalid metadata for reference: {link_path}")

        # A reference should be embedded unless explicitly set to false
        embed = metadata.get("embed", True)

        ref = ReferenceMatch(
            original_text=match.group(0),
            alt_text=alt_text,
            link_path=link_path,
            embed=embed,
            is_image=is_image,
            metadata=metadata
        )
        references.append(ref)

    return references
