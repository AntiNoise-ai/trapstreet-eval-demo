"""Template for plugging in your own agent / skill / MCP-driven loop.

Copy this file, edit `answer()`, then run:
    antinoise-eval run --agent your-agent

The runner only cares about the `answer()` signature. Everything else (tool
calls, retrieval, multi-step reasoning) is up to you.
"""

from __future__ import annotations

from .base import Agent, AgentResponse, QuestionContext


class YourAgent(Agent):
    name = "your-agent"

    def __init__(self) -> None:
        # Initialize your model client, tools, MCP connection, etc.
        pass

    def answer(self, ctx: QuestionContext) -> AgentResponse:
        # ctx.question        — the FinanceBench question
        # ctx.evidence        — list[str] of supporting passages
        # ctx.company         — e.g. "3M"
        # ctx.doc_name        — e.g. "3M_2018_10K"
        # ctx.doc_type        — e.g. "10K"
        # ctx.doc_period      — e.g. 2018
        #
        # Return an AgentResponse with at least `answer` set. Keep it short:
        # a number, percentage, currency amount, or short phrase.
        raise NotImplementedError(
            "Implement YourAgent.answer() to run this baseline. "
            "See agents/claude.py for a working reference."
        )
