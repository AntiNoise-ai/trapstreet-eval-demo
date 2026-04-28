"""Anthropic Claude baseline.

Uses the local `claude` CLI when available (your Claude Code session — no API
key needed). Falls back to the Anthropic SDK + ANTHROPIC_API_KEY otherwise.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time

from ..pdf_utils import truncate_to_chars
from .base import Agent, AgentResponse, QuestionContext

SYSTEM_PROMPT = (
    "You are a financial analyst answering questions from SEC filings. "
    "Return ONLY the answer — a number, percentage, currency amount, or short "
    "phrase. Do not explain. Do not show work. If the document does not "
    "contain the answer, reply 'unknown'."
)

# Per-1M-token pricing (USD). Updated 2026-Q1; only used by the API transport
# (CLI returns its own `total_cost_usd`).
PRICING = {
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00},
    "claude-opus-4-7": {"input": 15.00, "output": 75.00},
}

# Hard cap on context characters in PDF mode. Sonnet handles 200k tokens
# (~700k chars). Most 10-Ks fit; very long ones are head+tail truncated.
MAX_PDF_CHARS = 600_000

CLI_TIMEOUT_S = 300


def _claude_cli_available() -> bool:
    return shutil.which("claude") is not None


class ClaudeAgent(Agent):
    """Routes calls through `claude` CLI by default, Anthropic SDK as fallback.

    Transport selection:
      - `transport="cli"`  → require the `claude` binary
      - `transport="api"`  → require ANTHROPIC_API_KEY
      - `transport="auto"` (default) → CLI if available, otherwise API
    """

    def __init__(self, model: str = "claude-sonnet-4-6", transport: str = "auto") -> None:
        if transport == "auto":
            transport = "cli" if _claude_cli_available() else "api"

        if transport == "cli":
            if not _claude_cli_available():
                raise RuntimeError(
                    "`claude` CLI not found on PATH. Install Claude Code "
                    "(https://claude.ai/code) or set ANTHROPIC_API_KEY."
                )
            self._client = None
        elif transport == "api":
            try:
                from anthropic import Anthropic
            except ImportError as e:
                raise RuntimeError("Install anthropic: pip install anthropic") from e
            if not os.environ.get("ANTHROPIC_API_KEY"):
                raise RuntimeError(
                    "Neither `claude` CLI nor ANTHROPIC_API_KEY is available. "
                    "Run `claude login` (recommended) or set ANTHROPIC_API_KEY."
                )
            self._client = Anthropic()
        else:
            raise ValueError(f"Unknown transport: {transport}")

        self.transport = transport
        self.model = model
        self.name = f"{model} ({transport})"

    def answer(self, ctx: QuestionContext) -> AgentResponse:
        prompt = self._build_pdf_prompt(ctx) if ctx.mode == "pdf" else self._build_evidence_prompt(ctx)
        if self.transport == "cli":
            return self._answer_cli(prompt, ctx.mode)
        return self._answer_api(prompt, ctx.mode)

    # --- CLI transport --------------------------------------------------------

    def _answer_cli(self, prompt: str, mode: str) -> AgentResponse:
        cmd = [
            "claude", "-p",
            "--no-session-persistence",
            "--tools", "",
            "--output-format", "json",
            "--model", self.model,
            "--system-prompt", SYSTEM_PROMPT,
        ]
        start = time.time()
        try:
            proc = subprocess.run(
                cmd,
                input=prompt,
                capture_output=True,
                text=True,
                timeout=CLI_TIMEOUT_S,
            )
        except subprocess.TimeoutExpired:
            return AgentResponse(answer="", latency_ms=CLI_TIMEOUT_S * 1000, error="cli timeout")
        latency_ms = int((time.time() - start) * 1000)

        if proc.returncode != 0:
            return AgentResponse(
                answer="",
                latency_ms=latency_ms,
                error=f"cli exit {proc.returncode}: {proc.stderr.strip()[:300]}",
            )
        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError as e:
            return AgentResponse(
                answer="",
                latency_ms=latency_ms,
                error=f"cli bad json: {e}; stdout[:200]={proc.stdout[:200]!r}",
            )

        if data.get("is_error"):
            return AgentResponse(
                answer="",
                latency_ms=latency_ms,
                error=str(data.get("result") or data.get("subtype") or "cli error"),
            )

        usage = data.get("usage") or {}
        return AgentResponse(
            answer=str(data.get("result") or "").strip(),
            latency_ms=latency_ms,
            cost_usd=float(data.get("total_cost_usd") or 0.0),
            raw={
                "mode": mode,
                "transport": "cli",
                "model": self.model,
                "input_tokens": usage.get("input_tokens"),
                "output_tokens": usage.get("output_tokens"),
                "duration_api_ms": data.get("duration_api_ms"),
                "session_id": data.get("session_id"),
            },
        )

    # --- API transport --------------------------------------------------------

    def _answer_api(self, prompt: str, mode: str) -> AgentResponse:
        start = time.time()
        try:
            resp = self._client.messages.create(
                model=self.model,
                max_tokens=256,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as e:
            return AgentResponse(
                answer="",
                latency_ms=int((time.time() - start) * 1000),
                error=f"{type(e).__name__}: {e}",
            )
        latency_ms = int((time.time() - start) * 1000)
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()
        cost = self._cost(resp.usage.input_tokens, resp.usage.output_tokens)
        return AgentResponse(
            answer=text,
            latency_ms=latency_ms,
            cost_usd=cost,
            raw={
                "mode": mode,
                "transport": "api",
                "model": self.model,
                "input_tokens": resp.usage.input_tokens,
                "output_tokens": resp.usage.output_tokens,
            },
        )

    # --- Prompt builders ------------------------------------------------------

    def _build_evidence_prompt(self, ctx: QuestionContext) -> str:
        evidence_block = "\n\n---\n\n".join(ctx.evidence) if ctx.evidence else "(no evidence)"
        return (
            f"Company: {ctx.company} ({ctx.doc_type} {ctx.doc_period})\n\n"
            f"Evidence:\n{evidence_block}\n\n"
            f"Question: {ctx.question}\n\nAnswer:"
        )

    def _build_pdf_prompt(self, ctx: QuestionContext) -> str:
        body = truncate_to_chars(ctx.pdf_text, MAX_PDF_CHARS) if ctx.pdf_text else "(no PDF text)"
        return (
            f"Company: {ctx.company} ({ctx.doc_type} {ctx.doc_period})\n\n"
            f"Filing text (extracted from {ctx.doc_name}.pdf):\n"
            f"<<<\n{body}\n>>>\n\n"
            f"Question: {ctx.question}\n\nAnswer:"
        )

    def _cost(self, in_tokens: int, out_tokens: int) -> float:
        p = PRICING.get(self.model, {"input": 0.0, "output": 0.0})
        return (in_tokens / 1_000_000) * p["input"] + (out_tokens / 1_000_000) * p["output"]
