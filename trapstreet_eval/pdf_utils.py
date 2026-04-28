"""PDF download (on demand from patronus-ai/financebench) + text extraction with cache."""

from __future__ import annotations

import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Iterable

from .data import Question

PDF_BASE_URL = "https://raw.githubusercontent.com/patronus-ai/financebench/main/pdfs"


def download_pdf(doc_name: str, dest: Path, *, force: bool = False) -> Path:
    """Download a single FinanceBench PDF if not already present."""
    if dest.exists() and not force and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = f"{PDF_BASE_URL}/{doc_name}.pdf"
    try:
        with urllib.request.urlopen(url, timeout=60) as resp:
            dest.write_bytes(resp.read())
    except urllib.error.URLError as e:
        raise RuntimeError(f"Failed to download {url}: {e}") from e
    return dest


def ensure_pdfs(questions: Iterable[Question], *, log: bool = True) -> list[Path]:
    """Download every PDF referenced by `questions` (idempotent, deduped)."""
    seen: set[str] = set()
    paths: list[Path] = []
    for q in questions:
        if q.doc_name in seen:
            continue
        seen.add(q.doc_name)
        path = q.pdf_path
        if path.exists() and path.stat().st_size > 0:
            paths.append(path)
            continue
        if log:
            print(f"  ↓ {q.doc_name}.pdf", file=sys.stderr)
        download_pdf(q.doc_name, path)
        paths.append(path)
    return paths


def extract_text(pdf_path: Path, cache_path: Path | None = None) -> str:
    """Extract text from a PDF using pypdf. Cache to `cache_path` on first call."""
    if cache_path and cache_path.exists() and cache_path.stat().st_size > 0:
        return cache_path.read_text(encoding="utf-8")

    try:
        from pypdf import PdfReader
    except ImportError as e:
        raise RuntimeError(
            "pypdf not installed. Run: pip install -e '.[pdf]' (or pip install pypdf)"
        ) from e

    reader = PdfReader(str(pdf_path))
    pages_text: list[str] = []
    for page in reader.pages:
        try:
            pages_text.append(page.extract_text() or "")
        except Exception:
            pages_text.append("")
    text = "\n\n".join(pages_text).strip()

    if cache_path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(text, encoding="utf-8")
    return text


def truncate_to_chars(text: str, max_chars: int) -> str:
    """Trim text to a hard character budget. Keeps head + tail (boilerplate often at edges)."""
    if len(text) <= max_chars:
        return text
    head = max_chars * 2 // 3
    tail = max_chars - head
    return f"{text[:head]}\n\n[...truncated {len(text) - max_chars:,} chars...]\n\n{text[-tail:]}"
