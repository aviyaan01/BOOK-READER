"""PDF text extraction service using PyMuPDF."""

import os
from pathlib import Path
from typing import List, Tuple
import pymupdf as fitz
from backend.app.services.text_clean import clean_extracted_text


class PDFExtractionError(Exception):
    """Base exception for PDF extraction failures."""
    pass


class CorruptedPDFError(PDFExtractionError):
    """Raised when the PDF file is corrupted, malformed, or unreadable."""
    pass


class EncryptedPDFError(PDFExtractionError):
    """Raised when the PDF file is encrypted or password-protected."""
    pass


def extract_pages(pdf_path: str) -> Tuple[List[str], bool]:
    """Extract page text using PyMuPDF and detect if the document is likely scanned.

    Args:
        pdf_path: Path to the target PDF file.

    Returns:
        A tuple of (pages, is_scanned), where pages is a list of strings for each page
        and is_scanned is True if any page contains fewer than 20 characters of text.

    Raises:
        CorruptedPDFError: If the PDF cannot be opened or is corrupted.
        EncryptedPDFError: If the PDF is password-protected or encrypted.
        FileNotFoundError: If the PDF file does not exist.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found at: {pdf_path}")

    try:
        doc = fitz.open(pdf_path)
    except Exception as exc:
        raise CorruptedPDFError(f"Failed to open PDF at '{pdf_path}'. File may be corrupted or invalid.") from exc

    try:
        if doc.is_encrypted or doc.needs_pass:
            raise EncryptedPDFError(f"The PDF file at '{pdf_path}' is encrypted or password-protected.")

        total_pages = len(doc)
        if total_pages == 0:
            return [], True

        pages: List[str] = []
        is_scanned = False

        for page_num in range(total_pages):
            try:
                page = doc.load_page(page_num)
                page_text = page.get_text("text") or ""
            except Exception as exc:
                raise CorruptedPDFError(f"Failed reading page {page_num + 1} from '{pdf_path}'.") from exc

            cleaned = clean_extracted_text(page_text)
            pages.append(cleaned)

            # If a page has fewer than 20 characters of text, mark as likely scanned
            if len(cleaned.strip()) < 20:
                is_scanned = True

        return pages, is_scanned

    finally:
        doc.close()


def extract_text_from_pdf(pdf_path: str) -> Tuple[str, int, List[Tuple[int, str]]]:
    """Extract title, total page count, and non-empty page text tuples from a PDF file."""
    pages, _ = extract_pages(pdf_path)
    total_pages = len(pages)

    doc = fitz.open(pdf_path)
    metadata_title = (doc.metadata.get("title") or "").strip()
    doc.close()

    pages_data: List[Tuple[int, str]] = []
    first_meaningful_line = ""

    for idx, page_text in enumerate(pages):
        if page_text:
            pages_data.append((idx + 1, page_text))
            if not first_meaningful_line:
                lines = [l.strip() for l in page_text.split("\n") if len(l.strip()) > 2]
                if lines:
                    first_meaningful_line = lines[0]

    title = metadata_title or first_meaningful_line or Path(pdf_path).stem
    return title, total_pages, pages_data
