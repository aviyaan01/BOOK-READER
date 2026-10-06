"""PDF text extraction service using PyMuPDF and Tesseract OCR."""

import io
import logging
import os
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from PIL import Image
import pymupdf as fitz
import pytesseract

from backend.app.services.text_clean import clean_extracted_text

logger = logging.getLogger(__name__)

SCANNED_PDF_WARNING = (
    "This looks like a scanned PDF, text recognition may take longer and can contain errors."
)


class PDFExtractionError(Exception):
    """Base exception for PDF extraction failures."""
    pass


class CorruptedPDFError(PDFExtractionError):
    """Raised when the PDF file is corrupted, malformed, or unreadable."""
    pass


class EncryptedPDFError(PDFExtractionError):
    """Raised when the PDF file is encrypted or password-protected."""
    pass


class TesseractNotFoundError(PDFExtractionError):
    """Raised when Tesseract OCR binary or required language data is missing."""
    pass


def configure_tesseract() -> None:
    """Detect and configure Tesseract executable path if not already in PATH."""
    tesseract_env = os.environ.get("TESSERACT_CMD")
    if tesseract_env and os.path.exists(tesseract_env):
        pytesseract.pytesseract.tesseract_cmd = tesseract_env
        return

    # Check if currently configured binary or 'tesseract' is accessible
    current_cmd = getattr(pytesseract.pytesseract, "tesseract_cmd", "tesseract")
    if shutil.which(current_cmd) or shutil.which("tesseract"):
        return

    # Check common standard Windows installation directories
    common_windows_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.expanduser(r"~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"),
    ]
    for candidate in common_windows_paths:
        if os.path.exists(candidate):
            pytesseract.pytesseract.tesseract_cmd = candidate
            return


def check_tesseract_installed() -> None:
    """Verify that Tesseract OCR executable is available on the system."""
    configure_tesseract()
    cmd = getattr(pytesseract.pytesseract, "tesseract_cmd", "tesseract")
    if not (shutil.which(cmd) or os.path.exists(cmd)):
        raise TesseractNotFoundError(
            "Tesseract OCR is not installed or not found in system PATH. "
            "Please install Tesseract and language data (see README). "
            "Scanned PDF processing requires Tesseract OCR."
        )


def get_ocr_language(language: Optional[str]) -> str:
    """Determine the Tesseract OCR language string based on book language.

    Returns 'ben+eng' for Bangla, or 'eng' for English.
    """
    if not language:
        return "eng"
    lang_lower = str(language).strip().lower()
    if lang_lower in ("bn", "ben", "bangla") or "ben" in lang_lower:
        return "ben+eng"
    return "eng"


def extract_pages(
    pdf_path: str,
    language: str = "en",
    progress_callback: Optional[Callable[[int, int], None]] = None,
    on_scanned_detected: Optional[Callable[[], None]] = None,
    max_workers: Optional[int] = None,
) -> Tuple[List[str], bool]:
    """Extract page text using PyMuPDF and detect if the document is likely scanned.

    When is_scanned is True, renders each page to an image at 200 DPI with PyMuPDF
    and runs pytesseract with lang 'ben+eng' for Bangla, or 'eng' for English,
    processing pages concurrently in a thread pool and reporting progress.

    Args:
        pdf_path: Path to the target PDF file.
        language: Story language code ('bn'/'bangla' for Bengali, 'en' for English).
        progress_callback: Optional callback reporting OCR progress as (completed, total).
        on_scanned_detected: Optional callback invoked immediately when document is identified as scanned.
        max_workers: Max concurrent worker threads for OCR processing.

    Returns:
        A tuple of (pages, is_scanned), where pages is a list of strings for each page
        and is_scanned is True if any page contains fewer than 20 characters of text.

    Raises:
        CorruptedPDFError: If the PDF cannot be opened or is corrupted.
        EncryptedPDFError: If the PDF is password-protected or encrypted.
        FileNotFoundError: If the PDF file does not exist.
        TesseractNotFoundError: If OCR is required but Tesseract is not installed or language data missing.
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

    finally:
        doc.close()

    # When document is scanned, run OCR on all pages in a thread pool
    if is_scanned:
        logger.warning(SCANNED_PDF_WARNING)
        print(SCANNED_PDF_WARNING)

        if on_scanned_detected:
            try:
                on_scanned_detected()
            except Exception as err:
                logger.error("Error invoking on_scanned_detected callback: %s", err)

        check_tesseract_installed()
        ocr_lang = get_ocr_language(language)

        def _ocr_single_page(p_idx: int) -> Tuple[int, str]:
            """Render a page to image with PyMuPDF (200 DPI) and run pytesseract."""
            p_doc = fitz.open(pdf_path)
            try:
                p_page = p_doc.load_page(p_idx)
                # Render page to image with PyMuPDF at 200 DPI
                pix = p_page.get_pixmap(dpi=200)
                img = Image.open(io.BytesIO(pix.tobytes("png")))

                try:
                    raw_text = pytesseract.image_to_string(img, lang=ocr_lang)
                except (pytesseract.pytesseract.TesseractNotFoundError, FileNotFoundError) as t_err:
                    raise TesseractNotFoundError(
                        "Tesseract OCR is not installed or not in your PATH. "
                        "Please install Tesseract and language data (see README)."
                    ) from t_err
                except pytesseract.TesseractError as t_err:
                    err_msg = str(t_err)
                    if "traineddata" in err_msg or "ben" in err_msg:
                        raise TesseractNotFoundError(
                            f"Tesseract language data for '{ocr_lang}' is missing. "
                            "Please install Bangla language data (see README)."
                        ) from t_err
                    raise PDFExtractionError(f"Tesseract OCR recognition failed: {t_err}") from t_err

                return p_idx, clean_extracted_text(raw_text)
            finally:
                p_doc.close()

        ocr_pages = [""] * total_pages
        completed_count = 0
        workers = min(max_workers or 4, total_pages) if total_pages > 0 else 1

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(_ocr_single_page, p_idx): p_idx
                for p_idx in range(total_pages)
            }
            for future in as_completed(futures):
                p_idx, recognized_text = future.result()
                # Use recognized OCR text or fallback to original text if OCR text is empty
                ocr_pages[p_idx] = recognized_text or pages[p_idx]
                completed_count += 1
                logger.info("OCR progress: %d/%d pages processed", completed_count, total_pages)

                if progress_callback:
                    try:
                        progress_callback(completed_count, total_pages)
                    except TypeError:
                        try:
                            progress_callback(
                                completed_count,
                                total_pages,
                                f"OCR processing {completed_count}/{total_pages}",
                            )
                        except Exception:
                            pass

        pages = ocr_pages

    return pages, is_scanned


def extract_text_from_pdf(
    pdf_path: str,
    language: str = "en",
    progress_callback: Optional[Callable[[int, int], None]] = None,
    on_scanned_detected: Optional[Callable[[], None]] = None,
) -> Tuple[str, int, List[Tuple[int, str]]]:
    """Extract title, total page count, and non-empty page text tuples from a PDF file."""
    pages, _ = extract_pages(
        pdf_path,
        language=language,
        progress_callback=progress_callback,
        on_scanned_detected=on_scanned_detected,
    )
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
