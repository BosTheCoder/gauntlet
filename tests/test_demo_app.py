import re
from pathlib import Path

from fastapi.testclient import TestClient

from gauntlet.demo.app import create_app
from gauntlet.runner import run_suite
from gauntlet.suite import load_suite
from gauntlet.targets import build_target

SUITES = Path(__file__).resolve().parents[1] / "suites"


def client() -> TestClient:
    return TestClient(create_app())


def start_run(http, suite: str, hardened: bool) -> str:
    data = {"suite": suite}
    if hardened:
        data["hardened"] = "on"
    response = http.post("/runs", data=data)
    assert response.status_code == 200
    match = re.search(r"/runs/([0-9a-f]+)", response.text)
    assert match, response.text
    return match.group(1)


def finished(http, run_id: str) -> dict:
    for _ in range(200):
        payload = http.get(f"/runs/{run_id}.json").json()
        if payload["done"]:
            return payload
    raise AssertionError("run never finished")


def test_index_serves_the_cold_start_banner_on_first_paint():
    response = client().get("/")
    assert response.status_code == 200
    assert 'id="cold-start"' in response.text


def test_index_offers_both_suites_and_the_harden_toggle():
    body = client().get("/").text
    assert 'value="capability"' in body
    assert 'value="safety"' in body
    assert 'name="hardened"' in body


def test_a_run_through_the_web_surface_matches_the_library():
    http = client()
    payload = finished(http, start_run(http, "safety", hardened=False))
    library = run_suite(
        load_suite(SUITES / "safety.yaml"),
        target=build_target("python:gauntlet.demo.agent:vulnerable"),
    )
    web = {(c["id"], c["attack_id"]): c["passed"] for c in payload["report"]["cases"]}
    assert web == {(r.case_id, r.attack_id): r.passed for r in library.results}
    assert payload["report"]["overall_leak_rate"] == library.overall_leak_rate


def test_the_harden_toggle_drives_the_leak_rate_to_zero():
    http = client()
    before = finished(http, start_run(http, "safety", hardened=False))
    after = finished(http, start_run(http, "safety", hardened=True))
    assert before["report"]["overall_leak_rate"] > 0
    assert after["report"]["overall_leak_rate"] == 0.0
    assert after["report"]["target"].endswith(":defended")


def test_results_are_polled_while_running_and_stop_polling_when_done():
    http = client()
    run_id = start_run(http, "capability", hardened=False)
    finished(http, run_id)
    fragment = http.get(f"/runs/{run_id}").text
    assert "hx-trigger" not in fragment
    assert "refuses-unknown-restaurant" in fragment


def test_an_unknown_run_id_is_a_404():
    assert client().get("/runs/deadbeef.json").status_code == 404


def test_an_unknown_suite_name_is_rejected():
    assert client().post("/runs", data={"suite": "nope"}).status_code == 422
