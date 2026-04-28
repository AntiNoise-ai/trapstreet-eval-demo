"""Load FinanceBench questions from the local JSONL pulled by fetch_financebench.sh."""

from __future__ import annotations

import json
import random
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
FINANCEBENCH_JSONL = DATA_DIR / "financebench" / "data" / "financebench_open_source.jsonl"
SUBSET_JSONL = DATA_DIR / "subset.jsonl"
PDF_DIR = DATA_DIR / "financebench" / "pdfs"
PDF_TEXT_DIR = DATA_DIR / "financebench" / "pdf_text"


@dataclass(frozen=True)
class Question:
    """A single FinanceBench question, normalized for the demo runner."""

    id: str
    question: str
    answer: str
    evidence: tuple[str, ...]
    company: str
    doc_name: str
    doc_period: int | None
    doc_type: str
    question_type: str
    question_reasoning: str
    gics_sector: str | None

    @property
    def pdf_path(self) -> Path:
        """Where this question's source PDF lives once downloaded."""
        return PDF_DIR / f"{self.doc_name}.pdf"

    @property
    def pdf_text_path(self) -> Path:
        """Where the cached extracted text lives."""
        return PDF_TEXT_DIR / f"{self.doc_name}.txt"

    @classmethod
    def from_record(cls, rec: dict) -> "Question":
        evidence_list = rec.get("evidence") or []
        evidence_texts = tuple(
            e.get("evidence_text", "") for e in evidence_list if e.get("evidence_text")
        )
        return cls(
            id=str(rec["financebench_id"]),
            question=rec["question"],
            answer=rec["answer"],
            evidence=evidence_texts,
            company=rec.get("company", ""),
            doc_name=rec.get("doc_name", ""),
            doc_period=rec.get("doc_period"),
            doc_type=rec.get("doc_type", ""),
            question_type=rec.get("question_type", ""),
            question_reasoning=rec.get("question_reasoning", ""),
            gics_sector=rec.get("gics_sector"),
        )


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(
            f"Missing dataset at {path}.\n"
            f"Run: ./scripts/fetch_financebench.sh"
        )
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def load_full() -> list[Question]:
    return [Question.from_record(r) for r in _read_jsonl(FINANCEBENCH_JSONL)]


def load_subset() -> list[Question]:
    """Load the curated 15-question demo subset (build it on first call)."""
    if not SUBSET_JSONL.exists():
        build_subset()
    return [Question.from_record(r) for r in _read_jsonl(SUBSET_JSONL)]


def build_subset(n_per_type: int = 5, seed: int = 42) -> Path:
    """Sample a balanced subset across FinanceBench question_type buckets.

    FinanceBench OSS has three balanced types (50 each): `metrics-generated`,
    `domain-relevant`, `novel-generated`. We pick `n_per_type` from each,
    deterministically. Default total = 15.
    """
    full = _read_jsonl(FINANCEBENCH_JSONL)
    rng = random.Random(seed)

    by_bucket: dict[str, list[dict]] = defaultdict(list)
    for r in full:
        by_bucket[r.get("question_type", "unknown")].append(r)

    target_buckets = ["metrics-generated", "domain-relevant", "novel-generated"]
    chosen: list[dict] = []
    for bucket in target_buckets:
        pool = by_bucket.get(bucket, [])
        if not pool:
            continue
        sample = rng.sample(pool, min(n_per_type, len(pool)))
        chosen.extend(sample)

    if not chosen:
        chosen = rng.sample(full, min(15, len(full)))

    SUBSET_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with SUBSET_JSONL.open("w", encoding="utf-8") as f:
        for r in chosen:
            f.write(json.dumps(r) + "\n")

    return SUBSET_JSONL
