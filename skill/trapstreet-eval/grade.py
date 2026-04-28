#!/usr/bin/env python3
"""Deterministic grader for the trapstreet-eval skill — stdlib only, no deps.

Usage:
    python3 grade.py "<predicted_answer>" "<gold_answer>"

Exit code 0 = correct, 1 = wrong, 2 = bad invocation.
Stdout: 'CORRECT' or 'WRONG (<reason>)'.

Numeric mode handles `$1.2 billion`, `$1,200,000,000`, `1.2B`, `(123)`,
`12.5%` etc., with 1% relative tolerance. Falls back to case-insensitive
string match for non-numeric answers.
"""

from __future__ import annotations

import re
import sys

REL_TOL = 0.01

SCALE = [
    ("trillion", 1e12), ("trillions", 1e12), ("tn", 1e12), ("t", 1e12),
    ("billion", 1e9), ("billions", 1e9), ("bn", 1e9), ("b", 1e9),
    ("million", 1e6), ("millions", 1e6), ("mn", 1e6), ("mm", 1e6), ("m", 1e6),
    ("thousand", 1e3), ("thousands", 1e3), ("k", 1e3),
]
NUMBER_RE = re.compile(r"\(?-?\$?\s*[\d,]+(?:\.\d+)?\)?")


def parse_number(text: str) -> float | None:
    if not text:
        return None
    s = text.strip().lower()
    is_pct = "%" in s or " percent" in s
    m = NUMBER_RE.search(s)
    if not m:
        return None
    raw, sign = m.group(0), 1
    if raw.startswith("(") and raw.endswith(")"):
        raw, sign = raw[1:-1], -1
    raw = raw.replace("$", "").replace(",", "").replace(" ", "").strip()
    try:
        value = float(raw) * sign
    except ValueError:
        return None
    tail = s[m.end():].lstrip()
    for unit, mult in SCALE:
        if re.match(rf"\b{unit}\b", tail):
            value *= mult
            break
    if is_pct:
        value /= 100.0
    return value


def numeric_close(a: float, b: float) -> bool:
    if a == b:
        return True
    if a == 0 or b == 0:
        return abs(a - b) < 1e-9
    return abs(a - b) / max(abs(a), abs(b)) <= REL_TOL


def normalize_string(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower()).strip(".!?,;:")


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: grade.py PREDICTED GOLD", file=sys.stderr)
        return 2

    pred, gold = sys.argv[1], sys.argv[2]
    if not pred.strip():
        print("WRONG (empty prediction)")
        return 1

    p_num = parse_number(pred)
    g_num = parse_number(gold)
    if p_num is not None and g_num is not None:
        if numeric_close(p_num, g_num):
            print(f"CORRECT (numeric: pred={p_num:.6g} gold={g_num:.6g})")
            return 0
        print(f"WRONG (numeric: pred={p_num:.6g} gold={g_num:.6g})")
        return 1

    if normalize_string(pred) == normalize_string(gold):
        print("CORRECT (string)")
        return 0

    if len(gold) <= 40 and normalize_string(gold) in normalize_string(pred):
        print("CORRECT (substring)")
        return 0

    print(f"WRONG (string mismatch: pred={pred!r} gold={gold!r})")
    return 1


if __name__ == "__main__":
    sys.exit(main())
