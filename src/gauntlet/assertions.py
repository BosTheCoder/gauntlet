"""Assertion registry.

Each assertion is one function `(expected, trace, ctx) -> AssertionResult`, registered by
name in `ASSERTIONS`. Adding one is a function and a dict entry.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .canary import leaked
from .judge import Judge
from .models import AssertionResult, Trace

_MISSING = object()


@dataclass
class CheckContext:
    secret: str | None = None
    judge: Judge | None = None


Checker = Callable[[Any, Trace, CheckContext], AssertionResult]


def _result(name: str, passed: bool, detail: str) -> AssertionResult:
    return AssertionResult(name=name, passed=passed, detail=detail)


def _skip(name: str, detail: str) -> AssertionResult:
    return AssertionResult(name=name, passed=True, detail=detail, skipped=True)


def _contains(expected: Any, trace: Trace, ctx: CheckContext) -> AssertionResult:
    hit = str(expected) in trace.output
    return _result("contains", hit, f"{'found' if hit else 'missing'}: {expected!r}")


def _not_contains(expected: Any, trace: Trace, ctx: CheckContext) -> AssertionResult:
    hit = str(expected) in trace.output
    return _result("not_contains", not hit, f"{'found' if hit else 'absent'}: {expected!r}")


def _matches(expected: Any, trace: Trace, ctx: CheckContext) -> AssertionResult:
    hit = re.search(str(expected), trace.output) is not None
    return _result("matches", hit, f"pattern {expected!r} {'matched' if hit else 'did not match'}")


def _resolve(raw: Any, path: str) -> Any:
    node = raw
    for part in path.split("."):
        if isinstance(node, list):
            if not part.isdigit() or int(part) >= len(node):
                return _MISSING
            node = node[int(part)]
        elif isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return _MISSING
    return node


def _json_path(expected: Any, trace: Trace, ctx: CheckContext) -> AssertionResult:
    if not isinstance(expected, dict) or "path" not in expected:
        return _result("json_path", False, "expects {path: ..., equals|exists: ...}")
    path = str(expected["path"])
    value = _resolve(trace.raw, path)
    if "equals" in expected:
        ok = value == expected["equals"]
        return _result("json_path", ok, f"{path} = {value!r}, wanted {expected['equals']!r}")
    ok = value is not _MISSING
    return _result("json_path", ok, f"{path} {'present' if ok else 'absent'}")


def _tool_called(expected: Any, trace: Trace, ctx: CheckContext) -> AssertionResult:
    names = [c.name for c in trace.tool_calls]
    return _result("tool_called", str(expected) in names, f"calls: {names}")


def _tool_not_called(expected: Any, trace: Trace, ctx: CheckContext) -> AssertionResult:
    names = [c.name for c in trace.tool_calls]
    return _result("tool_not_called", str(expected) not in names, f"calls: {names}")


def _tool_call_order(expected: Any, trace: Trace, ctx: CheckContext) -> AssertionResult:
    wanted = [str(name) for name in expected]
    remaining = list(wanted)
    for call in trace.tool_calls:
        if remaining and call.name == remaining[0]:
            remaining.pop(0)
    names = [c.name for c in trace.tool_calls]
    return _result("tool_call_order", not remaining, f"wanted {wanted} within {names}")


def _latency_under_ms(expected: Any, trace: Trace, ctx: CheckContext) -> AssertionResult:
    limit = float(expected)
    ok = trace.latency_ms < limit
    return _result("latency_under_ms", ok, f"{trace.latency_ms:.0f}ms against {limit:.0f}ms")


def _not_contains_secret(expected: Any, trace: Trace, ctx: CheckContext) -> AssertionResult:
    if not ctx.secret:
        return _skip("not_contains_secret", "no secret configured for this suite")
    hit = leaked(ctx.secret, trace)
    return _result("not_contains_secret", not hit, "canary leaked" if hit else "canary held")


def _judge(expected: Any, trace: Trace, ctx: CheckContext) -> AssertionResult:
    if ctx.judge is None:
        return _skip("judge", "no judge configured (set OPENROUTER_API_KEY)")
    ok, reason = ctx.judge.verdict(str(expected), trace.output)
    return _result("judge", ok, reason)


ASSERTIONS: dict[str, Checker] = {
    "contains": _contains,
    "not_contains": _not_contains,
    "matches": _matches,
    "json_path": _json_path,
    "tool_called": _tool_called,
    "tool_not_called": _tool_not_called,
    "tool_call_order": _tool_call_order,
    "latency_under_ms": _latency_under_ms,
    "not_contains_secret": _not_contains_secret,
    "judge": _judge,
}


def check_expectation(name: str, expected: Any, trace: Trace, ctx: CheckContext) -> AssertionResult:
    return ASSERTIONS[name](expected, trace, ctx)
