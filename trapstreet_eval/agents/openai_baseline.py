"""OpenAI baseline — same task, different vendor, for the comparison story."""

from __future__ import annotations

import os
import time

from ..pdf_utils import truncate_to_chars
from .base import Agent, AgentResponse, QuestionContext
from .claude import SYSTEM_PROMPT

PRICING = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
}

# GPT-4o context window is 128k tokens (~400k chars). Leave headroom for prompt
# overhead and output. Anything over this gets head+tail truncation — agents
# that just dump the whole 10-K will hit this on the longer filings.
MAX_PDF_CHARS = 350_000


class OpenAIAgent(Agent):
    def __init__(self, model: str = "gpt-4o") -> None:
        try:
            from openai import OpenAI
        except ImportError as e:
            raise RuntimeError("Install openai: pip install openai") from e
        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY not set in environment.")
        self.client = OpenAI()
        self.model = model
        self.name = model

    def answer(self, ctx: QuestionContext) -> AgentResponse:
        if ctx.mode == "pdf":
            user_msg = self._build_pdf_prompt(ctx)
        else:
            user_msg = self._build_evidence_prompt(ctx)

        start = time.time()
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                max_tokens=256,
                temperature=0.0,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
            )
        except Exception as e:
            return AgentResponse(
                answer="",
                latency_ms=int((time.time() - start) * 1000),
                error=f"{type(e).__name__}: {e}",
            )
        latency_ms = int((time.time() - start) * 1000)
        text = (resp.choices[0].message.content or "").strip()
        usage = resp.usage
        cost = self._cost(usage.prompt_tokens, usage.completion_tokens)
        return AgentResponse(
            answer=text,
            latency_ms=latency_ms,
            cost_usd=cost,
            raw={
                "mode": ctx.mode,
                "input_tokens": usage.prompt_tokens,
                "output_tokens": usage.completion_tokens,
            },
        )

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
