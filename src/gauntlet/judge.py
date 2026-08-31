"""LLM-judge assertions, via any OpenAI-compatible chat completions endpoint.

Defaults to OpenRouter. There is no provider SDK here on purpose: the whole client is one
POST, which keeps it swappable and keeps the test suite off the network.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol

import httpx

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openai/gpt-4o-mini"

PROMPT = (
    "You are grading one reply from an AI agent against a rubric.\n"
    "Rubric: {rubric}\n\n"
    "Reply:\n{output}\n\n"
    "Answer with Y or N on the first line, then one short line of reasoning."
)


class Judge(Protocol):
    def verdict(self, rubric: str, output: str) -> tuple[bool, str]: ...


@dataclass
class HttpJudge:
    api_key: str
    model: str = DEFAULT_MODEL
    base_url: str = DEFAULT_BASE_URL
    timeout_s: float = 30.0

    def verdict(self, rubric: str, output: str) -> tuple[bool, str]:
        response = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "temperature": 0,
                "messages": [
                    {"role": "user", "content": PROMPT.format(rubric=rubric, output=output)}
                ],
            },
            timeout=self.timeout_s,
        )
        response.raise_for_status()
        text = response.json()["choices"][0]["message"]["content"].strip()
        return parse_verdict(text)


def parse_verdict(text: str) -> tuple[bool, str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    head = lines[0] if lines else ""
    reason = " ".join(lines[1:]) if len(lines) > 1 else head
    return head.upper().startswith("Y"), reason


def load_judge() -> Judge | None:
    """Build a judge from the environment, or None when no key is configured."""
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        return None
    return HttpJudge(
        api_key=key,
        model=os.environ.get("GAUNTLET_JUDGE_MODEL", DEFAULT_MODEL),
        base_url=os.environ.get("OPENROUTER_BASE_URL", DEFAULT_BASE_URL),
    )
