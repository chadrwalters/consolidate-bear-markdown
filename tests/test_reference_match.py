"""Tests for reference matching functionality."""

from src.reference_match import ReferenceMatch, find_markdown_references


def test_find_markdown_references_basic() -> None:
    """Test basic reference finding functionality."""
    content = """
    # Test Document

    Here's an image: ![Image](test/image.jpg)
    And a link: [Document](test/doc.pdf)
    Another image: ![](test/image2.png)
    """

    refs = find_markdown_references(content)
    assert len(refs) == 3

    # Check image with alt text
    assert refs[0] == ReferenceMatch(
        original_text="![Image](test/image.jpg)",
        alt_text="Image",
        link_path="test/image.jpg",
        embed=True,
        is_image=True,
        metadata={},
    )

    # Check link
    assert refs[1] == ReferenceMatch(
        original_text="[Document](test/doc.pdf)",
        alt_text="Document",
        link_path="test/doc.pdf",
        embed=True,
        is_image=False,
        metadata={},
    )

    # Check image without alt text
    assert refs[2] == ReferenceMatch(
        original_text="![](test/image2.png)",
        alt_text="",
        link_path="test/image2.png",
        embed=True,
        is_image=True,
        metadata={},
    )


def test_find_markdown_references_with_metadata() -> None:
    """Test reference finding with metadata."""
    content = """
    # Test Document

    A link with embed: [Doc](test.pdf)<!-- {"embed": true} -->
    A link without embed: [Doc2](test2.pdf)<!-- {"other": "value"} -->
    An image with metadata: ![Alt](img.jpg)<!-- {"width": 100} -->
    """

    refs = find_markdown_references(content)
    assert len(refs) == 3

    # Check link with embed metadata
    assert refs[0] == ReferenceMatch(
        original_text='[Doc](test.pdf)<!-- {"embed": true} -->',
        alt_text="Doc",
        link_path="test.pdf",
        embed=True,
        is_image=False,
        metadata={"embed": True},
    )

    # Check link without embed metadata
    assert refs[1] == ReferenceMatch(
        original_text='[Doc2](test2.pdf)<!-- {"other": "value"} -->',
        alt_text="Doc2",
        link_path="test2.pdf",
        embed=True,
        is_image=False,
        metadata={"other": "value"},
    )

    # Check image with metadata
    assert refs[2] == ReferenceMatch(
        original_text='![Alt](img.jpg)<!-- {"width": 100} -->',
        alt_text="Alt",
        link_path="img.jpg",
        embed=True,
        is_image=True,
        metadata={"width": 100},
    )


def test_find_markdown_references_invalid_metadata() -> None:
    """Test handling of invalid metadata."""
    content = """
    Invalid metadata: [Doc](test.pdf)<!-- {not json} -->
    """

    refs = find_markdown_references(content)
    assert len(refs) == 1
    assert refs[0] == ReferenceMatch(
        original_text="[Doc](test.pdf)<!-- {not json} -->",
        alt_text="Doc",
        link_path="test.pdf",
        embed=True,
        is_image=False,
        metadata={},
    )
