"""In-memory run records for the demo, so HTMX can poll a run as it progresses."""

from __future__ import annotations

import os
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..attacks import load_corpus, select
from ..models import CaseResult
from ..report import case_to_dict
from ..runner import RunConfig, plan, run_suite
from ..suite import load_suite
from ..targets import build_target

SUITE_DIR = Path(
    os.environ.get("GAUNTLET_SUITE_DIR", Path(__file__).resolve().parents[3] / "suites")
)
SUITES = {"capability": "capability.yaml", "safety": "safety.yaml"}
AGENTS = {
    False: "python:gauntlet.demo.agent:vulnerable",
    True: "python:gauntlet.demo.agent:defended",
}
MAX_RUNS = 50


@dataclass
class RunRecord:
    id: str
    suite: str
    hardened: bool
    total: int
    cases: list[dict[str, Any] | None]
    report: dict[str, Any] | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def done(self) -> bool:
        return self.report is not None

    @property
    def completed(self) -> list[dict[str, Any]]:
        with self.lock:
            return [case for case in self.cases if case is not None]


_RUNS: dict[str, RunRecord] = {}
_RUNS_LOCK = threading.Lock()


def get_run(run_id: str) -> RunRecord | None:
    with _RUNS_LOCK:
        return _RUNS.get(run_id)


def _remember(record: RunRecord) -> None:
    with _RUNS_LOCK:
        _RUNS[record.id] = record
        for stale in list(_RUNS)[:-MAX_RUNS]:
            del _RUNS[stale]


def start_run(suite_name: str, hardened: bool) -> RunRecord:
    """Kick a suite off on a background thread and hand back the record to poll."""
    suite = load_suite(SUITE_DIR / SUITES[suite_name])
    attacks = select(load_corpus(), suite.attacks) if suite.attacks else []
    total = len(plan(suite, attacks))
    record = RunRecord(
        id=uuid.uuid4().hex,
        suite=suite_name,
        hardened=hardened,
        total=total,
        cases=[None] * total,
    )
    _remember(record)

    def on_result(index: int, result: CaseResult) -> None:
        with record.lock:
            record.cases[index] = case_to_dict(result)

    def worker() -> None:
        report = run_suite(
            suite,
            target=build_target(AGENTS[hardened]),
            attacks=attacks,
            config=RunConfig(concurrency=4),
            on_result=on_result,
        )
        record.report = report.to_dict()

    threading.Thread(target=worker, daemon=True).start()
    return record
