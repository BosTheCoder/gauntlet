import httpx
import pytest

from gauntlet.targets import HttpTarget, PythonTarget, TargetError, TransportFailure, build_target


def stub_transport(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_build_target_picks_the_adapter_from_the_spec():
    assert isinstance(build_target("https://example.invalid/chat"), HttpTarget)
    assert isinstance(build_target("python:gauntlet.demo.agent:vulnerable"), PythonTarget)


def test_build_target_rejects_an_unknown_spec():
    with pytest.raises(TargetError):
        build_target("grpc://example.invalid")


def test_http_target_posts_the_input_and_reads_the_documented_contract():
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = httpx.Request("POST", "http://x", content=request.content).content
        return httpx.Response(
            200,
            json={
                "output": "Booked.",
                "tool_calls": [{"name": "reserve_table", "arguments": {"party": 4}}],
            },
        )

    target = HttpTarget("https://example.invalid/chat", client=stub_transport(handler))
    trace = target.call("book a table")
    assert trace.output == "Booked."
    assert [c.name for c in trace.tool_calls] == ["reserve_table"]
    assert trace.tool_calls[0].arguments == {"party": 4}
    assert trace.raw["output"] == "Booked."
    assert b"book a table" in seen["body"]  # type: ignore[operator]


def test_http_target_raises_transport_failure_on_a_connection_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    target = HttpTarget("https://example.invalid/chat", client=stub_transport(handler))
    with pytest.raises(TransportFailure):
        target.call("hi")


def test_http_target_raises_transport_failure_on_a_server_error():
    target = HttpTarget(
        "https://example.invalid/chat",
        client=stub_transport(lambda request: httpx.Response(503, text="nope")),
    )
    with pytest.raises(TransportFailure):
        target.call("hi")


def test_http_target_rejects_a_response_missing_output():
    target = HttpTarget(
        "https://example.invalid/chat",
        client=stub_transport(lambda request: httpx.Response(200, json={"reply": "hi"})),
    )
    with pytest.raises(TargetError):
        target.call("hi")


def echo(text: str) -> dict[str, object]:
    return {"output": f"echo: {text}", "tool_calls": [{"name": "noop", "arguments": {}}]}


def plain(text: str) -> str:
    return f"plain: {text}"


def test_python_target_calls_the_named_callable():
    trace = PythonTarget(f"{__name__}:echo").call("hi")
    assert trace.output == "echo: hi"
    assert [c.name for c in trace.tool_calls] == ["noop"]


def test_python_target_accepts_a_bare_string_reply():
    trace = PythonTarget(f"{__name__}:plain").call("hi")
    assert trace.output == "plain: hi"
    assert trace.tool_calls == []


def test_python_target_reports_a_missing_callable():
    with pytest.raises(TargetError):
        PythonTarget(f"{__name__}:not_here")


def test_latency_is_measured_on_the_trace():
    trace = PythonTarget(f"{__name__}:plain").call("hi")
    assert trace.latency_ms >= 0.0
