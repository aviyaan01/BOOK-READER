"""Text cleaning, normalization, and language detection utilities."""

import re
from collections import Counter
from typing import List, Set


# Standalone page number pattern matching English (0-9) and Bangla (০-৯) digits
PAGE_NUMBER_PATTERN = re.compile(
    r"^\s*(?:(?:page|পৃষ্ঠা|p\.)\s*)?[-–—~•*\[(]?\s*[0-9০-৯]+(?:\s*[/|\-–—]\s*[0-9০-৯]+)?\s*[-–—~•*\])]?\s*$",
    re.IGNORECASE,
)


def remove_control_and_zero_width(text: str) -> str:
    """Remove zero-width spaces, BOM, soft hyphens, and non-printable control characters."""
    # Strip zero-width space (\u200b), BOM (\ufeff), soft hyphen (\u00ad), and ascii control chars
    cleaned = re.sub(r"[\ufeff\u200b\u00ad\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    # Replace non-breaking spaces with standard space
    cleaned = cleaned.replace("\u00a0", " ")
    return cleaned


def is_standalone_page_number(line: str) -> bool:
    """Check if a line contains only a standalone page number in English or Bangla."""
    stripped = line.strip()
    if not stripped:
        return False
    return bool(PAGE_NUMBER_PATTERN.match(stripped))


def normalize_header_candidate(line: str) -> str:
    """Normalize a line for header/footer comparison by stripping digits and excess whitespace."""
    # Remove English and Bangla digits
    without_digits = re.sub(r"[0-9০-৯]", "", line)
    # Collapse whitespace
    normalized = re.sub(r"\s+", " ", without_digits).strip()
    return normalized


def detect_repeating_headers_footers(pages: List[str], threshold: float = 0.40) -> Set[str]:
    """Identify lines that repeat on more than the threshold fraction of pages (after stripping digits)."""
    total_pages = len(pages)
    if total_pages <= 1:
        return set()

    page_candidate_sets: List[Set[str]] = []

    for page in pages:
        cleaned_page = remove_control_and_zero_width(page)
        lines = [line.strip() for line in cleaned_page.splitlines() if line.strip()]
        page_set: Set[str] = set()
        for line in lines:
            if is_standalone_page_number(line):
                continue
            norm = normalize_header_candidate(line)
            # Must have meaningful content to be considered a header/footer
            if len(norm) >= 3:
                page_set.add(norm)
        page_candidate_sets.append(page_set)

    # Count page occurrences for each normalized candidate
    candidate_counts: Counter[str] = Counter()
    for p_set in page_candidate_sets:
        for candidate in p_set:
            candidate_counts[candidate] += 1

    repeating: Set[str] = {
        candidate
        for candidate, count in candidate_counts.items()
        if count >= 2 and (count / total_pages) > threshold
    }
    return repeating


def fix_hyphenated_linebreaks(text: str) -> str:
    """Fix words broken across linebreaks with hyphens (e.g. 'ba-\\nlo' -> 'balo')."""
    # Matches word characters in English and Bangla before and after a hyphen + newline
    pattern = r"([\w\u0980-\u09FF]+)-\s*\n\s*([\w\u0980-\u09FF]+)"
    return re.sub(pattern, r"\1\2", text)


def clean_pages(pages: List[str]) -> str:
    """Clean and normalize extracted pages into a coherent storybook text.

    1. Detects and removes repeating headers/footers (>40% of pages after stripping digits).
    2. Removes standalone page numbers (English and Bangla digits ০-৯).
    3. Fixes hyphenated line breaks ('ba-\\nlo' -> 'balo').
    4. Joins lines within paragraphs while keeping blank lines as paragraph breaks.
    5. Normalizes whitespace and strips zero-width/control characters.
    6. Keeps all story words unchanged.
    """
    if not pages:
        return ""

    repeating_headers = detect_repeating_headers_footers(pages, threshold=0.40)
    cleaned_page_texts: List[str] = []

    for page in pages:
        cleaned = remove_control_and_zero_width(page)
        lines = cleaned.splitlines()
        filtered_lines: List[str] = []

        for line in lines:
            stripped = line.strip()
            # Keep blank lines for paragraph separation
            if not stripped:
                filtered_lines.append("")
                continue

            # Remove standalone page numbers
            if is_standalone_page_number(stripped):
                continue

            # Remove repeating headers and footers
            norm = normalize_header_candidate(stripped)
            if norm and norm in repeating_headers:
                continue

            filtered_lines.append(stripped)

        page_str = "\n".join(filtered_lines).strip()
        if page_str:
            cleaned_page_texts.append(page_str)

    if not cleaned_page_texts:
        return ""

    # Combine pages with paragraph break
    combined_text = "\n\n".join(cleaned_page_texts)

    # Fix hyphenated line breaks across lines
    combined_text = fix_hyphenated_linebreaks(combined_text)

    # Split into paragraphs by blank lines
    raw_paragraphs = re.split(r"\n\s*\n+", combined_text)
    cleaned_paragraphs: List[str] = []

    for para in raw_paragraphs:
        # Join lines inside the paragraph with a single space
        lines = [line.strip() for line in para.splitlines() if line.strip()]
        if lines:
            para_text = " ".join(lines)
            # Normalize multiple spaces within the paragraph
            para_text = re.sub(r"[ \t]+", " ", para_text).strip()
            if para_text:
                cleaned_paragraphs.append(para_text)

    return "\n\n".join(cleaned_paragraphs)


def clean_extracted_text(raw_text: str) -> str:
    """Normalize extracted text for a single page or snippet."""
    if not raw_text:
        return ""
    return clean_pages([raw_text])


def detect_language(text: str) -> str:
    """Detect whether text is primarily Bangla ('bn') or English ('en')."""
    bangla_chars = len(re.findall(r"[\u0980-\u09FF]", text))
    latin_chars = len(re.findall(r"[a-zA-Z]", text))
    if bangla_chars > 0 and bangla_chars >= (latin_chars * 0.3):
        return "bn"
    return "en"
