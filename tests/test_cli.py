import json
from pathlib import Path

from typer.testing import CliRunner

from gauntlet.cli import app

SUITES = Path(__file__).resolve().parents[1] / "suites"
runner = CliRunner()


def test_run_exits_non_zero_when_a_case_fails(tmp_path):
    result = runner.invoke(
        app,
        ["run", str(SUITES / "safety.yaml"), "--report", str(tmp_path / "r.json")],
    )
    assert result.exit_code == 1


def test_run_exits_zero_when_everything_passes_and_writes_both_reports(tmp_path):
    result = runner.invoke(
        app,
        [
            "run",
            str(SUITES / "safety.yaml"),
            "--target",
            "python:gauntlet.demo.agent:defended",
            "--report",
            str(tmp_path / "r.json"),
            "--html",
            str(tmp_path / "r.html"),
        ],
    )
    assert result.exit_code == 0
    assert json.loads((tmp_path / "r.json").read_text())["overall_leak_rate"] == 0.0
    assert (tmp_path / "r.html").read_text().startswith("<!doctype html>")


def test_gate_exit_codes_follow_the_comparison(tmp_path):
    good = tmp_path / "good.json"
    bad = tmp_path / "bad.json"
    good.write_text(json.dumps({"capability_pass_rate": 1.0, "leak_rates": {"a": 0.0}}))
    bad.write_text(json.dumps({"capability_pass_rate": 1.0, "leak_rates": {"a": 0.1}}))
    assert runner.invoke(app, ["gate", str(good), "--baseline", str(good)]).exit_code == 0
    assert runner.invoke(app, ["gate", str(bad), "--baseline", str(good)]).exit_code == 1


def test_list_attacks_groups_by_family():
    result = runner.invoke(app, ["list-attacks"])
    assert result.exit_code == 0
    assert "instruction_override" in result.stdout
    assert "io-ignore-previous" in result.stdout


def test_a_malformed_suite_is_reported_rather_than_crashing_silently(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("name: x\ntarget: python:a:b\ncases: []\n")
    result = runner.invoke(app, ["run", str(bad)])
    assert result.exit_code != 0
