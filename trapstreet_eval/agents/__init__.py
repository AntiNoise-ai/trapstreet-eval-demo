"""Agent implementations and registry."""

from __future__ import annotations

from .base import Agent, AgentResponse, QuestionContext

__all__ = ["Agent", "AgentResponse", "QuestionContext", "load_agent"]


def load_agent(name: str) -> Agent:
    """Resolve an agent name to an instance.

    Recognized names:
      - naive
      - claude               (claude-sonnet-4-6)
      - claude-haiku
      - gpt-4o
      - gpt-4o-mini
      - your-agent
    """
    name = name.lower().strip()
    if name == "naive":
        from .naive import NaiveAgent
        return NaiveAgent()
    if name in ("claude", "claude-sonnet", "claude-sonnet-4-6"):
        from .claude import ClaudeAgent
        return ClaudeAgent(model="claude-sonnet-4-6")
    if name in ("claude-haiku", "haiku"):
        from .claude import ClaudeAgent
        return ClaudeAgent(model="claude-haiku-4-5")
    if name in ("gpt-4o", "gpt4o"):
        from .openai_baseline import OpenAIAgent
        return OpenAIAgent(model="gpt-4o")
    if name in ("gpt-4o-mini", "gpt4o-mini"):
        from .openai_baseline import OpenAIAgent
        return OpenAIAgent(model="gpt-4o-mini")
    if name in ("your-agent", "yours"):
        from .your_agent import YourAgent
        return YourAgent()
    raise ValueError(f"Unknown agent: {name}")
