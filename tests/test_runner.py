import threading
import time

import pytest

from gauntlet.models import Attack, Case, Suite, Trace
from gauntlet.runner import RunConfig, run_suite
from gauntlet.targets import TransportFailure


class RecordingTarget:
    """A target that counts calls and can be told to fail transport N times first."""

    spec = "python:test:recording"

    def __init__(self, output: str = "hello", transport_failures: int = 0):
        self.output = output
        self.remaining_failures = transport_failures
        self.calls: list[str] = []
        self._lock = threading.Lock()

    def call(self, text: str) -> Trace:
        with self._lock:
            self.calls.append(text)
            if self.remaining_failures > 0:
                self.remaining_failures -= 1
                raise TransportFailure("connection reset")
        return Trace(input=text, output=self.output)


def suite_with(*expect_per_case: list[dict]) -> Suite:
    cases = [
        Case(id=f"c{i}", input=f"input {i}", expect=expect)
        for i, expect in enumerate(expect_per_case)
    ]
    return Suite(name="s", target="python:test:recording", cases=cases)


def test_a_transport_error_is_retried_and_the_case_still_passes():
    target = RecordingTarget(transport_failures=2)
    report = run_suite(
        suite_with([{"contains": "hello"}]),
        target=target,
        config=RunConfig(retries=2),
    )
    assert len(target.calls) == 3
    assert report.results[0].passed
    assert report.results[0].trace.attempts == 3


def test_retries_are_exhausted_and_the_case_is_reported_as_an_error():
    target = RecordingTarget(transport_failures=5)
    report = run_suite(
        suite_with([{"contains": "hello"}]),
        target=target,
        config=RunConfig(retries=1),
    )
    assert len(target.calls) == 2
    assert report.results[0].error is not None
    assert report.results[0].failed


def test_a_failing_assertion_never_triggers_a_retry():
    target = RecordingTarget(output="goodbye")
    report = run_suite(
        suite_with([{"contains": "hello"}]),
        target=target,
        config=RunConfig(retries=3),
    )
    assert len(target.calls) == 1
    assert report.results[0].failed


class OutOfOrderTarget:
    """Later cases finish first, so completion order never matches suite order."""

    spec = "python:test:slow"

    def __init__(self, count: int):
        self.count = count

    def call(self, text: str) -> Trace:
        index = int(text.split()[-1])
        time.sleep((self.count - index) * 0.02)
        return Trace(input=text, output="hello")


@pytest.mark.parametrize("run", [1, 2])
def test_report_order_follows_the_suite_regardless_of_completion_order(run):
    suite = suite_with(*([{"contains": "hello"}] for _ in range(5)))
    report = run_suite(
        suite,
        target=OutOfOrderTarget(5),
        config=RunConfig(concurrency=5),
    )
    assert [r.case_id for r in report.results] == [c.id for c in suite.cases]


def test_completion_callback_fires_for_every_case():
    seen: list[str] = []
    suite = suite_with(*([{"contains": "hello"}] for _ in range(4)))
    run_suite(
        suite,
        target=OutOfOrderTarget(4),
        config=RunConfig(concurrency=4),
        on_result=lambda index, result: seen.append(result.case_id),
    )
    assert sorted(seen) == [c.id for c in suite.cases]


def test_templated_cases_are_expanded_once_per_attack_in_a_stable_order():
    suite = Suite(
        name="s",
        target="python:test:recording",
        kind="safety",
        secret="SK-1",
        attacks=["fam"],
        cases=[
            Case(id="a", input_template="read {{attack}}", expect=[{"contains": "hello"}]),
            Case(id="b", input_template="see {{attack}}", expect=[{"contains": "hello"}]),
        ],
    )
    attacks = [
        Attack(id="x", family="fam", payload="PAYLOAD-X", note="n"),
        Attack(id="y", family="fam", payload="PAYLOAD-Y", note="n"),
    ]
    target = RecordingTarget()
    report = run_suite(suite, target=target, attacks=attacks)
    assert [(r.case_id, r.attack_id) for r in report.results] == [
        ("a", "x"),
        ("a", "y"),
        ("b", "x"),
        ("b", "y"),
    ]
    assert "PAYLOAD-X" in report.results[0].input
    assert report.results[0].input.startswith("read ")


def test_concurrency_actually_overlaps_work():
    active = 0
    peak = 0
    lock = threading.Lock()

    class Overlapping:
        spec = "python:test:overlap"

        def call(self, text: str) -> Trace:
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            time.sleep(0.05)
            with lock:
                active -= 1
            return Trace(input=text, output="hello")

    suite = suite_with(*([{"contains": "hello"}] for _ in range(6)))
    run_suite(suite, target=Overlapping(), config=RunConfig(concurrency=6))
    assert peak > 1
