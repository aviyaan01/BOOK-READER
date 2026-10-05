"""Unit tests for text cleaning and normalization service."""

import pytest
from backend.app.services.text_clean import (
    clean_pages,
    is_standalone_page_number,
    fix_hyphenated_linebreaks,
    detect_repeating_headers_footers,
)


def test_repeating_headers_and_footers_removed():
    """Verify headers and footers appearing on more than 40% of pages are detected and stripped."""
    pages = [
        "The Forest Chronicles - Page 1\nOnce upon a time in a deep woods.\nFooter Note\n1",
        "The Forest Chronicles - Page 2\nThe brave bird flew across the river.\nFooter Note\n2",
        "The Forest Chronicles - Page 3\nIt carried golden seeds in its beak.\nFooter Note\n3",
    ]
    # Header repeats on 3/3 pages (100% > 40%), Footer Note on 3/3 pages
    cleaned = clean_pages(pages)

    assert "The Forest Chronicles" not in cleaned
    assert "Footer Note" not in cleaned
    assert "Once upon a time in a deep woods." in cleaned
    assert "The brave bird flew across the river." in cleaned
    assert "It carried golden seeds in its beak." in cleaned


def test_standalone_page_numbers_english():
    """Verify standalone English page numbers in various formats are removed."""
    pages = [
        "12\nOnce upon a time.\n- 12 -",
        "Page 34\nA magical rabbit hopped by.\n[ 34 ]",
        "p. 5\nNight fell upon the forest.\n5",
    ]
    cleaned = clean_pages(pages)

    assert "12" not in cleaned
    assert "34" not in cleaned
    assert "Page" not in cleaned
    assert "p. 5" not in cleaned
    assert "Once upon a time." in cleaned
    assert "A magical rabbit hopped by." in cleaned
    assert "Night fell upon the forest." in cleaned


def test_standalone_page_numbers_bangla():
    """Verify standalone Bangla page numbers (০-৯) and labels are removed."""
    pages = [
        "১২\nএকদা এক শান্ত সবুজ বন ছিল।\n- ১২ -",
        "পৃষ্ঠা ৩৪\nপাখিটি মিষ্টি সুরে গান গাইল।\n[ ৩৪ ]",
        "পৃষ্ঠা ৫\nচাঁদের আলোয় বন ভেসে গেল।\n৫",
    ]
    cleaned = clean_pages(pages)

    assert "১২" not in cleaned
    assert "৩৪" not in cleaned
    assert "পৃষ্ঠা" not in cleaned
    assert "একদা এক শান্ত সবুজ বন ছিল।" in cleaned
    assert "পাখিটি মিষ্টি সুরে গান গাইল।" in cleaned
    assert "চাঁদের আলোয় বন ভেসে গেল।" in cleaned


def test_hyphenated_line_breaks_english():
    """Verify hyphenated words broken across linebreaks are rejoined."""
    pages = [
        "The little girl wore a beau-\ntiful red cape while wan-\ndering in the woods."
    ]
    cleaned = clean_pages(pages)

    assert "beautiful" in cleaned
    assert "wandering" in cleaned
    assert "beau-\ntiful" not in cleaned
    assert "wan-\ndering" not in cleaned


def test_hyphenated_line_breaks_bangla():
    """Verify hyphenated Bangla words broken across linebreaks are properly rejoined."""
    pages = [
        "বনের মাঝে এক সু-\nন্দর নদী বয়ে চলেছে। ছোট ঘুঘুটি আনন্দ-\nভরে গান গাইল।"
    ]
    cleaned = clean_pages(pages)

    assert "সুন্দর" in cleaned
    assert "আনন্দভরে" in cleaned
    assert "সু-\nন্দর" not in cleaned
    assert "আনন্দ-\nভরে" not in cleaned


def test_paragraph_joining_and_blank_lines():
    """Verify lines inside paragraphs are joined with spaces, while blank lines remain paragraph separators."""
    pages = [
        "Line one of first paragraph.\nLine two of first paragraph.\n\n"
        "Line one of second paragraph.\nLine two of second paragraph."
    ]
    cleaned = clean_pages(pages)
    paragraphs = cleaned.split("\n\n")

    assert len(paragraphs) == 2
    assert paragraphs[0] == "Line one of first paragraph. Line two of first paragraph."
    assert paragraphs[1] == "Line one of second paragraph. Line two of second paragraph."


def test_zero_width_and_control_characters_removed():
    """Verify zero-width spaces, BOM, and control characters are removed while preserving words."""
    pages = [
        "\ufeffThe\u200b brave\u00ad knight\x00 rode through the\u00a0forest."
    ]
    cleaned = clean_pages(pages)

    assert "\ufeff" not in cleaned
    assert "\u200b" not in cleaned
    assert "\u00ad" not in cleaned
    assert "\x00" not in cleaned
    assert cleaned == "The brave knight rode through the forest."


def test_complete_bangla_story_cleaning():
    """Verify a complete multi-page Bangla story with headers, footers, and page numbers."""
    pages = [
        "ছোট্ট নীল ঘুঘু - অধ্যায় ১\nএকদা এক শান্ত বনে একটি ঘুঘু থাকত।\nসে রোজ সকালে মিষ্টি গান গাইত।\nবই প্রকাশনী\n১",
        "ছোট্ট নীল ঘুঘু - অধ্যায় ২\nএকদিন সে বনের ওপারে সোনালী নদী দেখতে পেল।\nনদীর রূপ দেখে সে মুগ্ধ হলো।\nবই প্রকাশনী\n২",
        "ছোট্ট নীল ঘুঘু - অধ্যায় ৩\nঘুঘুটি আনন্দে ডানা মেলে উড়ে গেল।\nসব পাখিরা তাকে শুভেচ্ছা জানাল।\nবই প্রকাশনী\n৩",
    ]
    cleaned = clean_pages(pages)

    # Repeating header and footer should be stripped
    assert "ছোট্ট নীল ঘুঘু - অধ্যায়" not in cleaned
    assert "বই প্রকাশনী" not in cleaned
    # Standalone Bangla page numbers stripped
    assert "\n১\n" not in cleaned
    assert "\n২\n" not in cleaned
    assert "\n৩\n" not in cleaned
    # Story sentences preserved and joined within page
    assert "একদা এক শান্ত বনে একটি ঘুঘু থাকত। সে রোজ সকালে মিষ্টি গান গাইত।" in cleaned
    assert "একদিন সে বনের ওপারে সোনালী নদী দেখতে পেল। নদীর রূপ দেখে সে মুগ্ধ হলো।" in cleaned
    assert "ঘুঘুটি আনন্দে ডানা মেলে উড়ে গেল। সব পাখিরা তাকে শুভেচ্ছা জানাল।" in cleaned
