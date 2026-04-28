"""Sanity-check baseline — answers '0' to every question.

Useful for verifying the grader doesn't accidentally pass everything.
"""

from __future__ import annotations

from .base import Agent, AgentResponse, QuestionContext


class NaiveAgent(Agent):
    name = "naive"

    def answer(self, ctx: QuestionContext) -> AgentResponse:
        return AgentResponse(answer="0", latency_ms=0, cost_usd=0.0)
