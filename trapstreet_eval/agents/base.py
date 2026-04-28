"""Agent contract — implement `answer()` to plug into the runner."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class QuestionContext:
    """Everything the runner hands to an agent for one question.

    Two evaluation modes:
      - `mode='evidence'`: gold passages from the FinanceBench annotation.
        Tests extraction quality on a clean input.
      - `mode='pdf'`: full 10-K text (the runner pre-extracts it from the
        PDF once and reuses it across agents). Tests retrieval + extraction
        on a real document — closer to the original FinanceBench task.
    """

    question: str
    company: str
    doc_name: str
    doc_type: str
    doc_period: int | None
    mode: str = "evidence"
    evidence: tuple[str, ...] = ()
    pdf_path: Path | None = None
    pdf_text: str = ""


@dataclass
class AgentResponse:
    answer: str
    latency_ms: int = 0
    cost_usd: float = 0.0
    raw: dict = field(default_factory=dict)
    error: str | None = None


class Agent(ABC):
    """Implement this to plug your agent/skill/MCP-driven loop into the eval."""

    name: str = "unnamed"
    supported_modes: tuple[str, ...] = ("evidence", "pdf")

    @abstractmethod
    def answer(self, ctx: QuestionContext) -> AgentResponse:
        raise NotImplementedError
