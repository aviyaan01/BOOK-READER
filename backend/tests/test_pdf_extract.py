"""Unit tests for pdf_extract service with OCR support."""

import os
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
import pymupdf as fitz

from backend.app.services.pdf_extract import (
    extract_pages,
    extract_text_from_pdf,
    get_ocr_language,
    configure_tesseract,
    check_tesseract_installed,
    SCANNED_PDF_WARNING,
    TesseractNotFoundError,
    CorruptedPDFError,
    EncryptedPDFError,
)


def test_scanned_pdf_warning_message():
    """Verify exact scanned PDF warning message string."""
    assert SCANNED_PDF_WARNING == (
        "This looks like a scanned PDF, text recognition may take longer and can contain errors."
    )


@pytest.mark.parametrize(
    "lang_input, expected_ocr_lang",
    [
        ("bn", "ben+eng"),
        ("ben", "ben+eng"),
        ("bangla", "ben+eng"),
        ("BANGLA", "ben+eng"),
        ("en", "eng"),
        ("eng", "eng"),
        ("english", "eng"),
        (None, "eng"),
        ("", "eng"),
    ],
)
def test_get_ocr_language(lang_input, expected_ocr_lang):
    """Verify language code resolution for Tesseract OCR."""
    assert get_ocr_language(lang_input) == expected_ocr_lang


def test_extract_pages_normal_document():
    """Verify normal digital PDF extracts text directly without triggering OCR."""
    pdf_path = Path("sample_books/english_story_whispering_tree.pdf")
    if not pdf_path.exists():
        pytest.skip("Sample PDF not found.")

    with patch("backend.app.services.pdf_extract.check_tesseract_installed") as mock_check:
        pages, is_scanned = extract_pages(str(pdf_path))
        assert not is_scanned
        assert len(pages) == 2
        assert "Whispering Willow" in pages[0]
        # Tesseract check should not even be called for non-scanned PDFs
        mock_check.assert_not_called()


def test_extract_pages_scanned_pdf_triggers_ocr(tmp_path):
    """Verify scanned PDF (pages without text) triggers OCR via thread pool at 200 DPI."""
    # Create a 2-page scanned PDF with no text layer (just empty pages)
    scanned_pdf = tmp_path / "scanned_sample.pdf"
    doc = fitz.open()
    doc.new_page(width=300, height=400)
    doc.new_page(width=300, height=400)
    doc.save(str(scanned_pdf))
    doc.close()

    progress_reports = []
    def on_progress(done, total):
        progress_reports.append((done, total))

    scanned_flag_called = []
    def on_scanned():
        scanned_flag_called.append(True)

    with patch("backend.app.services.pdf_extract.check_tesseract_installed"), \
         patch("pytesseract.image_to_string") as mock_ocr:
        # Simulate OCR output
        mock_ocr.side_effect = ["Recognized Page 1 Text", "Recognized Page 2 Text"]

        pages, is_scanned = extract_pages(
            str(scanned_pdf),
            language="en",
            progress_callback=on_progress,
            on_scanned_detected=on_scanned,
        )

        assert is_scanned is True
        assert len(pages) == 2
        assert "Recognized Page 1 Text" in pages[0]
        assert "Recognized Page 2 Text" in pages[1]
        assert len(scanned_flag_called) == 1
        assert len(progress_reports) == 2
        assert (2, 2) in progress_reports

        # Verify OCR language used for English was 'eng'
        for call_args in mock_ocr.call_args_list:
            assert call_args[1].get("lang") == "eng"


def test_extract_pages_scanned_pdf_bangla_language(tmp_path):
    """Verify Bangla scanned PDF runs pytesseract with lang 'ben+eng'."""
    scanned_pdf = tmp_path / "scanned_bangla.pdf"
    doc = fitz.open()
    doc.new_page(width=200, height=200)
    doc.save(str(scanned_pdf))
    doc.close()

    with patch("backend.app.services.pdf_extract.check_tesseract_installed"), \
         patch("pytesseract.image_to_string") as mock_ocr:
        mock_ocr.return_value = "একদা এক বনে"

        pages, is_scanned = extract_pages(str(scanned_pdf), language="bn")

        assert is_scanned is True
        assert "একদা এক বনে" in pages[0]
        # Verify lang="ben+eng" was passed
        mock_ocr.assert_called_once()
        _, kwargs = mock_ocr.call_args
        assert kwargs.get("lang") == "ben+eng"


def test_extract_pages_missing_tesseract_raises_error(tmp_path):
    """Verify TesseractNotFoundError is raised when Tesseract binary is absent."""
    scanned_pdf = tmp_path / "scanned_no_tess.pdf"
    doc = fitz.open()
    doc.new_page(width=200, height=200)
    doc.save(str(scanned_pdf))
    doc.close()

    with patch("backend.app.services.pdf_extract.check_tesseract_installed", side_effect=TesseractNotFoundError("Tesseract not installed")):
        with pytest.raises(TesseractNotFoundError):
            extract_pages(str(scanned_pdf))


def test_extract_pages_corrupted_file(tmp_path):
    """Verify CorruptedPDFError is raised on invalid file content."""
    corrupted_pdf = tmp_path / "corrupted.pdf"
    corrupted_pdf.write_bytes(b"NOT A REAL PDF HEADER")

    with pytest.raises(CorruptedPDFError):
        extract_pages(str(corrupted_pdf))


def test_extract_text_from_pdf_metadata_fallback():
    """Verify extract_text_from_pdf returns title, page count, and non-empty page tuples."""
    pdf_path = Path("sample_books/english_story_whispering_tree.pdf")
    if not pdf_path.exists():
        pytest.skip("Sample PDF not found.")

    title, total_pages, pages_data = extract_text_from_pdf(str(pdf_path))
    assert total_pages == 2
    assert len(pages_data) == 2
    assert "Whispering" in title
