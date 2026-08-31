"""Target adapters: the two ways gauntlet can reach an agent.

`http` posts JSON to an endpoint; `python` imports a callable and runs it in-process.
Both return a `Trace`. Adding a third (a subprocess adapter, say) is one class with a
`call` method plus one entry in `TARGETS`.
"""

from __future__ import annotations

import importlib
import time
from collections.abc import Callable
from typing import Any, Protocol

import httpx

from .models import ToolCall, Trace


class TargetError(ValueError):
    """The target is misconfigured or broke its response contract."""


class TransportFailure(RuntimeError):
    """The target could not be reached. Retryable; assertion failures are not."""


class Target(Protocol):
    spec: str

    def call(self, text: str) -> Trace: ...


def _tool_calls(raw: Any) -> list[ToolCall]:
    calls = raw.get("tool_calls") or [] if isinstance(raw, dict) else []
    if not isinstance(calls, list):
        raise TargetError("tool_calls must be a list")
    out: list[ToolCall] = []
    for call in calls:
        if not isinstance(call, dict) or "name" not in call:
            raise TargetError("each tool call needs a name")
        out.append(ToolCall(name=str(call["name"]), arguments=dict(call.get("arguments") or {})))
    return out


class HttpTarget:
    """POST `{"input": ...}` and read back `{"output": ..., "tool_calls": [...]}`."""

    def __init__(self, spec: str, timeout_s: float = 30.0, client: httpx.Client | None = None):
        self.spec = spec
        self._client = client or httpx.Client(timeout=timeout_s)

    def call(self, text: str) -> Trace:
        started = time.perf_counter()
        try:
            response = self._client.post(self.spec, json={"input": text})
        except httpx.HTTPError as exc:
            raise TransportFailure(str(exc)) from exc
        elapsed_ms = (time.perf_counter() - started) * 1000
        if response.status_code >= 500:
            raise TransportFailure(f"{response.status_code} from target")
        if response.status_code >= 400:
            raise TargetError(f"{response.status_code} from target: {response.text[:200]}")
        try:
            raw = response.json()
        except ValueError as exc:
            raise TargetError("target did not return JSON") from exc
        if not isinstance(raw, dict) or not isinstance(raw.get("output"), str):
            raise TargetError("target response needs a string 'output' field")
        return Trace(
            input=text,
            output=raw["output"],
            tool_calls=_tool_calls(raw),
            latency_ms=elapsed_ms,
            raw=raw,
        )


class PythonTarget:
    """Call `module:callable` in-process. The callable takes the input text."""

    def __init__(self, spec: str):
        self.spec = spec
        path = spec.removeprefix("python:")
        module_name, _, attr = path.partition(":")
        if not module_name or not attr:
            raise TargetError(f"python target must look like module:callable, got {spec!r}")
        try:
            module = importlib.import_module(module_name)
        except ImportError as exc:
            raise TargetError(f"cannot import {module_name!r}: {exc}") from exc
        fn = getattr(module, attr, None)
        if not callable(fn):
            raise TargetError(f"{module_name}:{attr} is not callable")
        self._fn = fn

    def call(self, text: str) -> Trace:
        started = time.perf_counter()
        raw = self._fn(text)
        elapsed_ms = (time.perf_counter() - started) * 1000
        if isinstance(raw, str):
            raw = {"output": raw}
        if not isinstance(raw, dict) or not isinstance(raw.get("output"), str):
            raise TargetError("python target must return a string or a dict with 'output'")
        return Trace(
            input=text,
            output=raw["output"],
            tool_calls=_tool_calls(raw),
            latency_ms=elapsed_ms,
            raw=raw,
        )


TARGETS: dict[str, Callable[[str, float], Target]] = {
    "http": lambda spec, timeout_s: HttpTarget(spec, timeout_s=timeout_s),
    "https": lambda spec, timeout_s: HttpTarget(spec, timeout_s=timeout_s),
    "python": lambda spec, timeout_s: PythonTarget(spec),
}


def build_target(spec: str, timeout_s: float = 30.0) -> Target:
    scheme = spec.split(":", 1)[0]
    adapter = TARGETS.get(scheme)
    if adapter is None:
        raise TargetError(
            f"unrecognised target {spec!r}: use an http(s) URL or python:module:callable"
        )
    return adapter(spec, timeout_s)
