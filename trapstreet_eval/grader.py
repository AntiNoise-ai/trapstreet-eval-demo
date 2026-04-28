"""Grade an agent's answer against the FinanceBench gold answer.

Strategy:
1. Try to parse both as numbers (handles units, currency, percent, parens-negative).
2. If both numeric, compare with a relative tolerance (default 1%).
3. Otherwise, fall back to an LLM judge — short prompt, low cost.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import Optional

REL_TOLERANCE = 0.01  # 1% — tight but forgiving of rounding/unit reformatting

# Multipliers for unit suffixes commonly seen in 10-K answers.
SCALE = {
    "thousand": 1e3,
    "thousands": 1e3,
    "k": 1e3,
    "million": 1e6,
    "millions": 1e6,
    "mn": 1e6,
    "mm": 1e6,
    "m": 1e6,
    "billion": 1e9,
    "billions": 1e9,
    "bn": 1e9,
    "b": 1e9,
    "trillion": 1e12,
    "trillions": 1e12,
    "tn": 1e12,
    "t": 1e12,
}

# A signed decimal: $1,234.56 / -1.234 / (123) / 12,345
_NUMBER = r"\(?-?\$?\s*[\d,]+(?:\.\d+)?\)?"


@dataclass(frozen=True)
class GradeResult:
    correct: bool
    method: str  # "numeric" | "llm_judge" | "string" | "error"
    detail: str = ""


def _strip_parens_negative(s: str) -> tuple[str, int]:
    """Convert '(123)' → ('123', -1). Otherwise sign=1."""
    s = s.strip()
    if s.startswith("(") and s.endswith(")"):
        return s[1:-1], -1
    return s, 1


def parse_number(text: str) -> Optional[float]:
    """Pull the first numeric value out of `text`, applying unit scale and percent.

    Returns None if no parseable number is found.
    """
    if not text:
        return None
    t = text.strip().lower()
    is_percent = "%" in t or " percent" in t

    m = re.search(_NUMBER, t)
    if not m:
        return None

    raw = m.group(0)
    raw, sign = _strip_parens_negative(raw)
    raw = raw.replace("$", "").replace(",", "").replace(" ", "").strip()
    try:
        value = float(raw) * sign
    except ValueError:
        return None

    # Apply unit scale if a suffix follows the number.
    tail = t[m.end():].strip()
    for unit, mult in sorted(SCALE.items(), key=lambda kv: -len(kv[0])):
        if re.match(rf"\b{unit}\b", tail):
            value *= mult
            break

    if is_percent:
        # Normalize "12.5%" → 0.125 so we compare apples to apples.
        value = value / 100.0
    return value


def numeric_close(a: float, b: float, rel_tol: float = REL_TOLERANCE) -> bool:
    if a == b:
        return True
    if a == 0 or b == 0:
        return abs(a - b) < 1e-9
    return abs(a - b) / max(abs(a), abs(b)) <= rel_tol


def _normalize_string(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower()).strip(".!?,;:")


def _string_match(pred: str, gold: str) -> bool:
    p = _normalize_string(pred)
    g = _normalize_string(gold)
    if not p or not g:
        return False
    if p == g:
        return True
    # Common short-answer cases: yes/no, qualitative.
    short = {"yes", "no"}
    if g in short and p in short:
        return p == g
    # Substring on either side, but only for very short golds (avoid false positives).
    if len(g) <= 40 and g in p:
        return True
    return False


def grade(prediction: str, gold: str, question: str = "", use_judge: bool = True) -> GradeResult:
    """Return whether `prediction` matches `gold` for `question`."""
    if not prediction or not prediction.strip():
        return GradeResult(False, "error", "empty prediction")

    p_num = parse_number(prediction)
    g_num = parse_number(gold)
    if p_num is not None and g_num is not None:
        ok = numeric_close(p_num, g_num)
        return GradeResult(ok, "numeric", f"pred={p_num:.6g} gold={g_num:.6g}")

    if _string_match(prediction, gold):
        return GradeResult(True, "string", "exact/substring")

    if use_judge:
        if shutil.which("claude") is not None:
            return _llm_judge_cli(prediction, gold, question)
        if os.environ.get("ANTHROPIC_API_KEY"):
            return _llm_judge_api(prediction, gold, question)

    return GradeResult(False, "string", "no match, judge unavailable")


def _judge_prompt(prediction: str, gold: str, question: str) -> str:
    return (
        "You are grading a financial QA system. Answer ONLY 'YES' or 'NO'.\n\n"
        f"Question: {question}\n"
        f"Gold answer: {gold}\n"
        f"Predicted answer: {prediction}\n\n"
        "Is the predicted answer factually equivalent to the gold answer "
        "(allowing for rounding, unit, or wording differences)?"
    )


def _llm_judge_cli(prediction: str, gold: str, question: str) -> GradeResult:
    """LLM judge via the local `claude` CLI — uses your Claude Code session."""
    model = os.environ.get("TRAPSTREET_JUDGE_MODEL", "claude-haiku-4-5")
    cmd = [
        "claude", "-p",
        "--no-session-persistence",
        "--tools", "",
        "--output-format", "json",
        "--model", model,
    ]
    try:
        proc = subprocess.run(
            cmd,
            input=_judge_prompt(prediction, gold, question),
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        return GradeResult(False, "error", "judge cli timeout")
    if proc.returncode != 0:
        return GradeResult(False, "error", f"judge cli exit {proc.returncode}: {proc.stderr.strip()[:160]}")
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        return GradeResult(False, "error", f"judge cli bad json: {e}")
    out = str(data.get("result") or "").strip().upper()
    ok = out.startswith("YES")
    return GradeResult(ok, "llm_judge", f"cli model={model} out={out!r}")


def _llm_judge_api(prediction: str, gold: str, question: str) -> GradeResult:
    """LLM judge via the Anthropic SDK — used when `claude` CLI isn't installed."""
    try:
        from anthropic import Anthropic
    except ImportError:
        return GradeResult(False, "error", "anthropic SDK missing for judge")
    model = os.environ.get("TRAPSTREET_JUDGE_MODEL", "claude-haiku-4-5")
    try:
        client = Anthropic()
        resp = client.messages.create(
            model=model,
            max_tokens=4,
            messages=[{"role": "user", "content": _judge_prompt(prediction, gold, question)}],
        )
        out = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip().upper()
        ok = out.startswith("YES")
        return GradeResult(ok, "llm_judge", f"api model={model} out={out!r}")
    except Exception as e:
        return GradeResult(False, "error", f"judge api failed: {e}")
