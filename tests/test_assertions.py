"""Every assertion type gets a pass case and a fail case against a hand-built trace."""

import pytest

from gauntlet.assertions import ASSERTIONS, CheckContext, check_expectation
from gauntlet.models import ToolCall, Trace

TRACE = Trace(
    input="book a table for four at 7pm",
    output="Booked. Reference AB12. Your table is at 19:00.",
    tool_calls=[
        ToolCall(name="reserve_table", arguments={"party": 4, "time": "19:00"}),
        ToolCall(name="send_email", arguments={"to": "guest"}),
    ],
    latency_ms=120.0,
    raw={"output": "Booked.", "meta": {"agent": "concierge", "version": 2}},
)


class StubJudge:
    def __init__(self, verdict: bool, reason: str = "because") -> None:
        self._verdict = verdict
        self.reason = reason
        self.calls: list[tuple[str, str]] = []

    def verdict(self, rubric: str, output: str) -> tuple[bool, str]:
        self.calls.append((rubric, output))
        return self._verdict, self.reason


def run(name, expected, ctx=None):
    return check_expectation(name, expected, TRACE, ctx or CheckContext())


PASS_CASES = [
    ("contains", "Reference AB12"),
    ("not_contains", "sorry"),
    ("matches", r"Reference [A-Z]{2}\d{2}"),
    ("json_path", {"path": "meta.agent", "equals": "concierge"}),
    ("tool_called", "reserve_table"),
    ("tool_not_called", "cancel_table"),
    ("tool_call_order", ["reserve_table", "send_email"]),
    ("latency_under_ms", 4000),
]

FAIL_CASES = [
    ("contains", "Reference ZZ99"),
    ("not_contains", "Booked"),
    ("matches", r"Reference \d{4}"),
    ("json_path", {"path": "meta.agent", "equals": "other"}),
    ("tool_called", "cancel_table"),
    ("tool_not_called", "reserve_table"),
    ("tool_call_order", ["send_email", "reserve_table"]),
    ("latency_under_ms", 10),
]


@pytest.mark.parametrize(("name", "expected"), PASS_CASES)
def test_assertion_passes(name, expected):
    assert run(name, expected).passed


@pytest.mark.parametrize(("name", "expected"), FAIL_CASES)
def test_assertion_fails(name, expected):
    assert not run(name, expected).passed


def test_json_path_exists_form():
    assert run("json_path", {"path": "meta.version", "exists": True}).passed
    assert not run("json_path", {"path": "meta.missing", "exists": True}).passed


def test_json_path_indexes_into_lists():
    trace = Trace(input="", output="", raw={"items": [{"id": "a"}, {"id": "b"}]})
    ctx = CheckContext()
    assert check_expectation("json_path", {"path": "items.1.id", "equals": "b"}, trace, ctx).passed


def test_not_contains_secret_passes_when_clean_and_fails_when_leaked():
    ctx = CheckContext(secret="SK-CANARY-9F2A")
    assert run("not_contains_secret", True, ctx).passed
    leaky = Trace(input="", output="key SK-CANARY-9F2A")
    assert not check_expectation("not_contains_secret", True, leaky, ctx).passed


def test_not_contains_secret_without_a_configured_secret_is_skipped():
    result = run("not_contains_secret", True, CheckContext(secret=None))
    assert result.skipped


def test_judge_uses_the_configured_client_and_reports_its_verdict():
    yes, no = StubJudge(True), StubJudge(False)
    assert run("judge", "Confirms the booking", CheckContext(judge=yes)).passed
    assert not run("judge", "Confirms the booking", CheckContext(judge=no)).passed
    assert yes.calls[0][1] == TRACE.output


def test_judge_is_skipped_when_no_client_is_configured():
    result = run("judge", "Confirms the booking", CheckContext(judge=None))
    assert result.skipped


def test_every_registered_assertion_is_covered_by_a_pass_and_a_fail_case():
    covered = {n for n, _ in PASS_CASES} | {"not_contains_secret", "judge"}
    assert covered == set(ASSERTIONS)
