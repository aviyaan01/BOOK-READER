"""Sentence chunking and narrative text packing service."""

import re
from typing import List, Dict, Any


def split_sentences(text: str, language: str = "en") -> List[str]:
    """Split text into sentences respecting '.', '!', '?', and Bangla danda '।'.

    Protects abbreviations (e.g. 'Mr.', 'Dr.') and decimal numbers (e.g. '3.5', '৪.৫')
    from false sentence boundaries.
    """
    if not text or not text.strip():
        return []

    # Protect decimals with English digits (3.5) and Bangla digits (৪.৫)
    protected = re.sub(r"([\d০-৯])\.([\d০-৯])", r"\1__DECIMAL__\2", text)

    # Protect common abbreviations and titles
    abbr_pattern = r"\b(Mr|Mrs|Ms|Dr|Prof|Sr|Jr|vs|etc|e\.g|i\.e)\.\s*"
    protected = re.sub(abbr_pattern, lambda m: m.group(0).replace(".", "__DOT__"), protected)

    # Protect single uppercase letter initials (e.g. "J. K. Rowling", "A. B.")
    protected = re.sub(r"\b([A-Z])\.\s*", r"\1__INIT__ ", protected)

    # Mark sentence boundaries after punctuation and optional closing quote/bracket
    boundary_pattern = r"([.!?।॥][\"'”’\)\]]?)\s+"
    delimited = re.sub(boundary_pattern, r"\1__SENT_SPLIT__", protected)

    raw_sentences = delimited.split("__SENT_SPLIT__")

    sentences: List[str] = []
    for s in raw_sentences:
        # Restore protected characters
        restored = s.replace("__DECIMAL__", ".").replace("__DOT__", ".").replace("__INIT__", ".").strip()
        if restored:
            sentences.append(restored)

    return sentences


def split_by_words(text: str, max_chars: int) -> List[str]:
    """Fallback utility to split a clause or word sequence at whitespace boundaries."""
    words = text.split(" ")
    parts: List[str] = []
    current = ""

    for w in words:
        if not w:
            continue
        candidate = f"{current} {w}" if current else w
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                parts.append(current)
            if len(w) > max_chars:
                for i in range(0, len(w), max_chars):
                    parts.append(w[i:i + max_chars])
                current = ""
            else:
                current = w

    if current:
        parts.append(current)
    return parts


def split_long_sentence(sentence: str, max_chars: int) -> List[str]:
    """Split a sentence longer than max_chars at the nearest comma boundary."""
    if len(sentence) <= max_chars:
        return [sentence]

    # Split by comma (standard ',' and full-width '，') keeping the comma with the preceding clause
    boundary_pattern = r"([,，])\s+"
    delimited = re.sub(boundary_pattern, r"\1__COMMA_SPLIT__", sentence)
    clauses = [c.strip() for c in delimited.split("__COMMA_SPLIT__") if c.strip()]

    # If no commas exist, fallback to word boundary splitting
    if len(clauses) <= 1:
        return split_by_words(sentence, max_chars)

    sub_chunks: List[str] = []
    current = ""

    for clause in clauses:
        if len(clause) > max_chars:
            if current:
                sub_chunks.append(current)
                current = ""
            sub_chunks.extend(split_by_words(clause, max_chars))
            continue

        candidate = f"{current} {clause}" if current else clause
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                sub_chunks.append(current)
            current = clause

    if current:
        sub_chunks.append(current)

    return sub_chunks


def chunk_text(text: str, max_chars: int = 1000) -> List[str]:
    """Split text into paragraphs and sentences, packing whole sentences up to max_chars.

    Rules:
    - Split into paragraphs first, then sentences.
    - Sentence endings are '.', '!', '?', and the Bangla danda '।'.
    - Does not split on abbreviations like 'Mr.' or decimals like '3.5'.
    - Packs whole sentences up to max_chars.
    - If a sentence exceeds max_chars, splits at the nearest comma boundary.
    - Prefers starting a new chunk at a paragraph boundary.
    - Returns chunks in order with no empty strings.
    """
    if not text or not text.strip():
        return []

    # 1. Split into paragraphs first
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n+", text) if p.strip()]
    if not paragraphs:
        return []

    # 2. Split each paragraph into sentences and ensure each sentence <= max_chars
    para_sentences: List[List[str]] = []
    for para in paragraphs:
        sents = split_sentences(para)
        bounded_sents: List[str] = []
        for s in sents:
            if len(s) > max_chars:
                bounded_sents.extend(split_long_sentence(s, max_chars))
            else:
                bounded_sents.append(s)
        if bounded_sents:
            para_sentences.append(bounded_sents)

    # 3. Pack sentences into chunks up to max_chars, preferring paragraph boundaries
    chunks: List[str] = []
    current_chunk = ""

    for sents in para_sentences:
        if not sents:
            continue

        para_text = " ".join(sents)

        # If current_chunk already has text, check if the entire new paragraph fits
        if current_chunk:
            candidate = f"{current_chunk}\n\n{para_text}"
            if len(candidate) <= max_chars:
                current_chunk = candidate
                continue
            else:
                # The entire paragraph does not fit in remaining space.
                # Prefer starting a new chunk at the paragraph boundary!
                chunks.append(current_chunk)
                current_chunk = ""

        # If current_chunk is empty and paragraph fits as a whole:
        if len(para_text) <= max_chars:
            current_chunk = para_text
        else:
            # Paragraph itself exceeds max_chars; pack sentence by sentence
            for s in sents:
                if not current_chunk:
                    current_chunk = s
                elif len(current_chunk) + 1 + len(s) <= max_chars:
                    current_chunk = f"{current_chunk} {s}"
                else:
                    chunks.append(current_chunk)
                    current_chunk = s

    if current_chunk:
        chunks.append(current_chunk)

    return [c.strip() for c in chunks if c.strip()]


def chunk_page_text(page_text: str, page_number: int, language: str, start_index: int = 1) -> List[Dict[str, Any]]:
    """Convert page text into indexed chunk dictionaries."""
    sentences = split_sentences(page_text, language)
    chunks: List[Dict[str, Any]] = []
    current_index = start_index

    for s in sentences:
        chunks.append({
            "chunk_index": current_index,
            "page_number": page_number,
            "text": s,
            "audio_status": "pending",
            "audio_path": None,
        })
        current_index += 1

    return chunks
