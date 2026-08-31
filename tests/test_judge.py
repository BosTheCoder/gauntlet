import pytest

from gauntlet.judge import HttpJudge, load_judge, parse_verdict
from gauntlet.models import Case, Suite
from gauntlet.runner import run_suite
from gauntlet.targets import build_target


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Y\nit confirmed the booking", True),
        ("yes", True),
        ("N\nit refused", False),
        ("No, it did not", False),
        ("", False),
    ],
)
def test_verdict_parsing(text, expected):
    assert parse_verdict(text)[0] is expected


def test_verdict_reason_falls_back_to_the_single_line():
    assert parse_verdict("Y")[1] == "Y"
    assert parse_verdict("Y\nbooked the table")[1] == "booked the table"


def test_load_judge_returns_nothing_without_a_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    assert load_judge() is None


def test_load_judge_reads_the_key_and_overrides_from_the_environment(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    monkeypatch.setenv("GAUNTLET_JUDGE_MODEL", "some/model")
    monkeypatch.setenv("OPENROUTER_BASE_URL", "https://gateway.invalid/v1")
    judge = load_judge()
    assert isinstance(judge, HttpJudge)
    assert (judge.model, judge.base_url) == ("some/model", "https://gateway.invalid/v1")


class StubJudge:
    def __init__(self, verdict: bool):
        self.verdict_value = verdict
        self.rubrics: list[str] = []

    def verdict(self, rubric: str, output: str) -> tuple[bool, str]:
        self.rubrics.append(rubric)
        return self.verdict_value, "stubbed"


def echo(text: str) -> str:
    return "I could not find that restaurant."


def _suite() -> Suite:
    return Suite(
        name="s",
        target=f"python:{__name__}:echo",
        cases=[Case(id="c", input="book somewhere", expect=[{"judge": "Politely declines"}])],
    )


def test_a_judge_assertion_runs_through_the_stubbed_client():
    judge = StubJudge(True)
    report = run_suite(_suite(), target=build_target(f"python:{__name__}:echo"), judge=judge)
    assert report.results[0].passed
    assert judge.rubrics == ["Politely declines"]


def test_a_negative_judge_verdict_fails_the_case():
    report = run_suite(
        _suite(), target=build_target(f"python:{__name__}:echo"), judge=StubJudge(False)
    )
    assert report.results[0].failed


def test_without_a_judge_the_assertion_is_skipped_and_counted_as_such():
    report = run_suite(_suite(), target=build_target(f"python:{__name__}:echo"))
    assert report.results[0].passed
    assert report.to_dict()["counts"]["skipped_assertions"] == 1
