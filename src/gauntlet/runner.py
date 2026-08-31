"""The runner: expand a suite into cases, hit the target concurrently, check assertions."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from .assertions import CheckContext, check_expectation
from .attacks import load_corpus, select
from .judge import Judge
from .models import Attack, Case, CaseResult, Suite, Trace
from .report import Report
from .targets import Target, TransportFailure, build_target


@dataclass(frozen=True)
class RunConfig:
    concurrency: int = 8
    retries: int = 2
    timeout_s: float = 30.0


@dataclass(frozen=True)
class PlannedCase:
    case: Case
    text: str
    attack: Attack | None = None


def plan(suite: Suite, attacks: list[Attack]) -> list[PlannedCase]:
    """Case-major expansion, so the report order always follows the suite file."""
    planned: list[PlannedCase] = []
    for case in suite.cases:
        if case.input_template is None:
            planned.append(PlannedCase(case=case, text=case.input or ""))
            continue
        for attack in attacks:
            text = case.input_template.replace("{{attack}}", attack.payload)
            planned.append(PlannedCase(case=case, text=text, attack=attack))
    return planned


def _invoke(target: Target, text: str, retries: int) -> Trace:
    last: Exception | None = None
    for attempt in range(1, retries + 2):
        try:
            trace = target.call(text)
        except TransportFailure as exc:
            last = exc
            continue
        trace.attempts = attempt
        return trace
    raise TransportFailure(str(last))


def _run_one(item: PlannedCase, target: Target, ctx: CheckContext, config: RunConfig) -> CaseResult:
    try:
        trace = _invoke(target, item.text, config.retries)
    except Exception as exc:  # noqa: BLE001 - a broken target is a case failure, not a crash
        return CaseResult(
            case_id=item.case.id,
            input=item.text,
            trace=Trace(input=item.text, output=""),
            assertions=[],
            attack_id=item.attack.id if item.attack else None,
            family=item.attack.family if item.attack else None,
            remediation=item.attack.remediation if item.attack else None,
            error=f"{type(exc).__name__}: {exc}",
        )
    checks = [
        check_expectation(next(iter(expect)), next(iter(expect.values())), trace, ctx)
        for expect in item.case.expect
    ]
    return CaseResult(
        case_id=item.case.id,
        input=item.text,
        trace=trace,
        assertions=checks,
        attack_id=item.attack.id if item.attack else None,
        family=item.attack.family if item.attack else None,
        remediation=item.attack.remediation if item.attack else None,
    )


def run_suite(
    suite: Suite,
    *,
    target: Target | None = None,
    attacks: list[Attack] | None = None,
    judge: Judge | None = None,
    config: RunConfig | None = None,
    on_result: Callable[[int, CaseResult], None] | None = None,
) -> Report:
    config = config or RunConfig()
    if attacks is None:
        attacks = select(load_corpus(), suite.attacks) if suite.attacks else []
    target = target or build_target(suite.target, timeout_s=config.timeout_s)
    ctx = CheckContext(secret=suite.secret, judge=judge)
    items = plan(suite, attacks)

    results: dict[int, CaseResult] = {}
    with ThreadPoolExecutor(max_workers=max(1, config.concurrency)) as pool:
        futures = {
            pool.submit(_run_one, item, target, ctx, config): index
            for index, item in enumerate(items)
        }
        for future in as_completed(futures):
            index = futures[future]
            results[index] = future.result()
            if on_result is not None:
                on_result(index, results[index])
    return Report(
        suite=suite.name,
        kind=suite.kind,
        target=target.spec,
        results=[results[i] for i in range(len(items))],
    )
