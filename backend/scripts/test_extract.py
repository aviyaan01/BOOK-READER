"""CLI test script to extract and inspect PDF pages using extract_pages service."""

import sys
from pathlib import Path

# Ensure UTF-8 output on Windows consoles
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure backend package can be imported
workspace_root = Path(__file__).resolve().parent.parent.parent
if str(workspace_root) not in sys.path:
    sys.path.insert(0, str(workspace_root))

from backend.app.services.pdf_extract import (
    extract_pages,
    CorruptedPDFError,
    EncryptedPDFError,
    TesseractNotFoundError,
    PDFExtractionError,
    SCANNED_PDF_WARNING,
)


def run_extraction_test(pdf_path: str, language: str = "en") -> None:
    """Extract pages from a target PDF file and print summary metrics."""
    def on_progress(done: int, total: int) -> None:
        print(f"  [OCR Progress] Processed {done}/{total} pages...")

    try:
        pages, is_scanned = extract_pages(
            pdf_path,
            language=language,
            progress_callback=on_progress,
        )
    except FileNotFoundError as err:
        print(f"Error: {err}", file=sys.stderr)
        sys.exit(1)
    except EncryptedPDFError as err:
        print(f"Encrypted PDF Error: {err}", file=sys.stderr)
        sys.exit(1)
    except CorruptedPDFError as err:
        print(f"Corrupted PDF Error: {err}", file=sys.stderr)
        sys.exit(1)
    except TesseractNotFoundError as err:
        print(f"Tesseract OCR Error: {err}", file=sys.stderr)
        sys.exit(1)
    except PDFExtractionError as err:
        print(f"PDF Extraction Error: {err}", file=sys.stderr)
        sys.exit(1)
    except Exception as err:
        print(f"Unexpected Error: {err}", file=sys.stderr)
        sys.exit(1)

    all_text = "\n\n".join(pages).strip()
    first_500_chars = all_text[:500]

    print("=" * 50)
    print(f"PDF Path: {pdf_path}")
    print(f"Language: {language}")
    print(f"Page Count: {len(pages)}")
    print(f"Likely Scanned: {is_scanned}")
    if is_scanned:
        print(f"Notice: {SCANNED_PDF_WARNING}")
    print("=" * 50)
    print("First 500 Characters:")
    print("-" * 50)
    print(first_500_chars if first_500_chars else "[No extractable text found]")
    print("-" * 50)


def main() -> None:
    """Parse command line arguments and execute the extraction test."""
    if len(sys.argv) < 2:
        print("Usage: python backend/scripts/test_extract.py <path_to_pdf> [language]")
        sys.exit(1)

    pdf_file = sys.argv[1]
    language = sys.argv[2] if len(sys.argv) > 2 else "en"
    run_extraction_test(pdf_file, language=language)


if __name__ == "__main__":
    main()
