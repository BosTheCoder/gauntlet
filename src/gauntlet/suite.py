"""Suite loading and validation.

A suite is YAML. Bad suites fail here, at load time, rather than half way through a run.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .assertions import ASSERTIONS
from .models import Case, Suite


class SuiteError(ValueError):
    """A suite file is malformed."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SuiteError(message)


def _parse_case(raw: Any, index: int) -> Case:
    _require(isinstance(raw, dict), f"case {index} is not a mapping")
    case_id = raw.get("id")
    _require(isinstance(case_id, str) and bool(case_id), f"case {index} has no id")
    has_input = "input" in raw
    has_template = "input_template" in raw
    _require(
        has_input != has_template,
        f"case {case_id!r} needs exactly one of input or input_template",
    )
    if has_template:
        _require(
            "{{attack}}" in str(raw["input_template"]),
            f"case {case_id!r} input_template must contain {{{{attack}}}}",
        )
    expect = raw.get("expect")
    _require(isinstance(expect, list) and bool(expect), f"case {case_id!r} has no expectations")
    for item in expect:
        _require(
            isinstance(item, dict) and len(item) == 1,
            f"case {case_id!r}: each expectation is a single-key mapping",
        )
        name = next(iter(item))
        _require(name in ASSERTIONS, f"case {case_id!r}: unknown assertion {name!r}")
    return Case(
        id=str(case_id),
        expect=list(expect),
        input=raw.get("input"),
        input_template=raw.get("input_template"),
    )


def parse_suite(raw: Any) -> Suite:
    _require(isinstance(raw, dict), "suite must be a mapping")
    _require(isinstance(raw.get("name"), str), "suite needs a name")
    _require(isinstance(raw.get("target"), str), "suite needs a target")
    raw_cases = raw.get("cases")
    _require(isinstance(raw_cases, list) and bool(raw_cases), "suite needs at least one case")
    cases = [_parse_case(item, i) for i, item in enumerate(raw_cases)]
    ids = [c.id for c in cases]
    _require(len(set(ids)) == len(ids), "case ids must be unique")
    attacks = raw.get("attacks") or []
    _require(isinstance(attacks, list), "attacks must be a list of family names")
    templated = any(c.input_template for c in cases)
    _require(
        not templated or bool(attacks),
        "a suite with input_template cases needs an attacks list",
    )
    return Suite(
        name=raw["name"],
        target=raw["target"],
        cases=cases,
        kind="safety" if attacks else "capability",
        secret=raw.get("secret"),
        attacks=[str(a) for a in attacks],
    )


def load_suite(path: str | Path) -> Suite:
    text = Path(path).read_text()
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise SuiteError(f"{path}: {exc}") from exc
    return parse_suite(raw)
