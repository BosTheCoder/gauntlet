"""Core data types shared by the loader, runner, assertions and report."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass
class Trace:
    """One target invocation: what went in, what came back, how long it took."""

    input: str
    output: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    latency_ms: float = 0.0
    raw: dict[str, Any] = field(default_factory=dict)
    attempts: int = 1


@dataclass(frozen=True)
class Attack:
    id: str
    family: str
    payload: str
    note: str
    remediation: str = ""


@dataclass(frozen=True)
class Case:
    id: str
    expect: list[dict[str, Any]]
    input: str | None = None
    input_template: str | None = None


@dataclass(frozen=True)
class Suite:
    name: str
    target: str
    cases: list[Case]
    kind: str = "capability"
    secret: str | None = None
    attacks: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AssertionResult:
    name: str
    passed: bool
    detail: str
    skipped: bool = False


@dataclass
class CaseResult:
    case_id: str
    input: str
    trace: Trace
    assertions: list[AssertionResult]
    attack_id: str | None = None
    family: str | None = None
    remediation: str | None = None
    error: str | None = None

    @property
    def failed(self) -> bool:
        return self.error is not None or any(
            not a.passed and not a.skipped for a in self.assertions
        )

    @property
    def passed(self) -> bool:
        return not self.failed
