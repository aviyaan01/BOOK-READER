"""Service modules package for PDF extraction, cleaning, chunking, and TTS synthesis."""

from backend.app.services.chunker import chunk_text, split_sentences, chunk_page_text
from backend.app.services.text_clean import clean_pages, clean_extracted_text, detect_language
from backend.app.services.pdf_extract import (
    extract_pages,
    extract_text_from_pdf,
    SCANNED_PDF_WARNING,
    TesseractNotFoundError,
    get_ocr_language,
)
from backend.app.services.llm_clean import (
    clean_text_with_llm,
    clean_segment_with_llm,
    split_into_segments,
    is_valid_output_length,
    compute_segment_hash,
)

__all__ = [
    "chunk_text",
    "split_sentences",
    "chunk_page_text",
    "clean_pages",
    "clean_extracted_text",
    "detect_language",
    "extract_pages",
    "extract_text_from_pdf",
    "SCANNED_PDF_WARNING",
    "TesseractNotFoundError",
    "get_ocr_language",
    "clean_text_with_llm",
    "clean_segment_with_llm",
    "split_into_segments",
    "is_valid_output_length",
    "compute_segment_hash",
]
