"""Report assembly and the headline numbers the gate compares."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .models import CaseResult


def _rate(passed: int, total: int) -> float | None:
    return None if total == 0 else round(passed / total, 4)


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(fraction * len(ordered) + 0.5) - 1))
    return round(ordered[index], 2)


@dataclass
class Report:
    suite: str
    kind: str
    target: str
    results: list[CaseResult]
    generated_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds")
    )

    @property
    def capability_pass_rate(self) -> float | None:
        plain = [r for r in self.results if r.attack_id is None]
        return _rate(sum(1 for r in plain if r.passed), len(plain))

    @property
    def leak_rates(self) -> dict[str, float]:
        rates: dict[str, float] = {}
        for family in dict.fromkeys(r.family for r in self.results if r.family):
            rows = [r for r in self.results if r.family == family]
            rates[str(family)] = round(sum(1 for r in rows if r.failed) / len(rows), 4)
        return rates

    @property
    def overall_leak_rate(self) -> float | None:
        rows = [r for r in self.results if r.attack_id is not None]
        return _rate(sum(1 for r in rows if r.failed), len(rows))

    def to_dict(self) -> dict[str, Any]:
        latencies = [r.trace.latency_ms for r in self.results if r.error is None]
        return {
            "suite": self.suite,
            "kind": self.kind,
            "target": self.target,
            "generated_at": self.generated_at,
            "capability_pass_rate": self.capability_pass_rate,
            "leak_rates": self.leak_rates,
            "overall_leak_rate": self.overall_leak_rate,
            "latency_p50_ms": _percentile(latencies, 0.5),
            "latency_p95_ms": _percentile(latencies, 0.95),
            "counts": {
                "cases": len(self.results),
                "passed": sum(1 for r in self.results if r.passed),
                "failed": sum(1 for r in self.results if r.failed),
                "skipped_assertions": sum(
                    1 for r in self.results for a in r.assertions if a.skipped
                ),
            },
            "cases": [case_to_dict(r) for r in self.results],
        }

    def write_json(self, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.to_dict(), indent=2) + "\n")


def case_to_dict(result: CaseResult) -> dict[str, Any]:
    return {
        "id": result.case_id,
        "attack_id": result.attack_id,
        "family": result.family,
        "remediation": result.remediation,
        "input": result.input,
        "output": result.trace.output,
        "tool_calls": [{"name": c.name, "arguments": c.arguments} for c in result.trace.tool_calls],
        "latency_ms": round(result.trace.latency_ms, 2),
        "attempts": result.trace.attempts,
        "error": result.error,
        "passed": result.passed,
        "assertions": [
            {"name": a.name, "passed": a.passed, "skipped": a.skipped, "detail": a.detail}
            for a in result.assertions
        ],
    }


def load_report(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text())
