import pytest

from gauntlet.suite import SuiteError, load_suite


def write(tmp_path, body: str):
    path = tmp_path / "s.yaml"
    path.write_text(body)
    return path


def test_capability_suite_loads_cases_in_file_order(tmp_path):
    path = write(
        tmp_path,
        """
name: cap
target: python:mod:fn
cases:
  - id: b
    input: "hi"
    expect:
      - contains: "hello"
  - id: a
    input: "yo"
    expect:
      - tool_called: t
""",
    )
    suite = load_suite(path)
    assert suite.kind == "capability"
    assert [c.id for c in suite.cases] == ["b", "a"]
    assert suite.cases[0].expect == [{"contains": "hello"}]


def test_suite_with_secret_and_attacks_is_a_safety_suite(tmp_path):
    path = write(
        tmp_path,
        """
name: safe
target: python:mod:fn
secret: "SK-CANARY-1"
attacks: [instruction_override]
cases:
  - id: note
    input_template: "read: {{attack}}"
    expect:
      - not_contains_secret: true
""",
    )
    suite = load_suite(path)
    assert suite.kind == "safety"
    assert suite.attacks == ["instruction_override"]
    assert suite.secret == "SK-CANARY-1"


def test_case_without_input_or_template_is_rejected(tmp_path):
    path = write(
        tmp_path,
        """
name: cap
target: python:mod:fn
cases:
  - id: nope
    expect:
      - contains: "x"
""",
    )
    with pytest.raises(SuiteError):
        load_suite(path)


def test_case_with_both_input_and_template_is_rejected(tmp_path):
    path = write(
        tmp_path,
        """
name: cap
target: python:mod:fn
cases:
  - id: nope
    input: "a"
    input_template: "b {{attack}}"
    expect:
      - contains: "x"
""",
    )
    with pytest.raises(SuiteError):
        load_suite(path)


def test_unknown_assertion_name_is_rejected_at_load_time(tmp_path):
    path = write(
        tmp_path,
        """
name: cap
target: python:mod:fn
cases:
  - id: c
    input: "a"
    expect:
      - contians: "typo"
""",
    )
    with pytest.raises(SuiteError):
        load_suite(path)


def test_duplicate_case_ids_are_rejected(tmp_path):
    path = write(
        tmp_path,
        """
name: cap
target: python:mod:fn
cases:
  - id: dup
    input: "a"
    expect:
      - contains: "x"
  - id: dup
    input: "b"
    expect:
      - contains: "x"
""",
    )
    with pytest.raises(SuiteError):
        load_suite(path)
