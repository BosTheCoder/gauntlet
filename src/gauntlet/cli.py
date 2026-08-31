"""The `gauntlet` command line."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from .attacks import BUILTIN_FAMILIES, load_corpus, select
from .gate import gate as evaluate_gate
from .html_report import write_html
from .judge import load_judge
from .report import load_report
from .runner import RunConfig, run_suite
from .suite import load_suite
from .targets import build_target

app = typer.Typer(add_completion=False, help="Capability and safety evals for LLM agents.")


@app.command()
def run(
    suite_file: Annotated[Path, typer.Argument(help="Suite YAML file.")],
    target: Annotated[str | None, typer.Option(help="Override the suite's target.")] = None,
    attacks: Annotated[Path | None, typer.Option(help="Extra attack directory.")] = None,
    report: Annotated[Path | None, typer.Option(help="Write report.json here.")] = None,
    html: Annotated[
        Path | None, typer.Option(help="Write a self-contained report.html here.")
    ] = None,
    concurrency: Annotated[int, typer.Option(help="Cases in flight at once.")] = 8,
    retries: Annotated[int, typer.Option(help="Retries on transport errors only.")] = 2,
    timeout: Annotated[float, typer.Option(help="Per-request timeout in seconds.")] = 30.0,
) -> None:
    """Run a suite and print the headline numbers."""
    suite = load_suite(suite_file)
    corpus = load_corpus(attacks)
    selected = select(corpus, suite.attacks) if suite.attacks else []
    result = run_suite(
        suite,
        target=build_target(target or suite.target, timeout_s=timeout),
        attacks=selected,
        judge=load_judge(),
        config=RunConfig(concurrency=concurrency, retries=retries, timeout_s=timeout),
    )
    payload = result.to_dict()
    if report:
        result.write_json(report)
    if html:
        write_html(payload, html)
    _print_summary(payload)
    raise typer.Exit(0 if payload["counts"]["failed"] == 0 else 1)


@app.command()
def gate(
    report_file: Annotated[Path, typer.Argument(help="Report from this run.")],
    baseline: Annotated[Path, typer.Option(help="Report to compare against.")],
    max_drop: Annotated[float, typer.Option(help="Capability drop allowed, in points.")] = 2.0,
) -> None:
    """Fail the build on a capability drop past the band, or any leak-rate rise."""
    result = evaluate_gate(load_report(report_file), load_report(baseline), max_drop)
    for note in result.notes:
        typer.echo(f"  ok   {note}")
    for reason in result.reasons:
        typer.secho(f"  FAIL {reason}", fg=typer.colors.RED)
    typer.echo("gate passed" if result.ok else "gate failed")
    raise typer.Exit(0 if result.ok else 1)


@app.command("list-attacks")
def list_attacks(
    attacks: Annotated[Path | None, typer.Option(help="Extra attack directory.")] = None,
) -> None:
    """List the attack corpus, grouped by family, with each family's remediation."""
    corpus = load_corpus(attacks)
    families = sorted(
        {a.family for a in corpus},
        key=lambda f: (
            BUILTIN_FAMILIES.index(f) if f in BUILTIN_FAMILIES else len(BUILTIN_FAMILIES),
            f,
        ),
    )
    for family in families:
        entries = [a for a in corpus if a.family == family]
        typer.secho(f"\n{family}", bold=True)
        typer.echo(f"  fix: {entries[0].remediation}")
        for attack in entries:
            typer.echo(f"  - {attack.id}: {attack.note}")


def _print_summary(payload: dict) -> None:
    counts = payload["counts"]
    typer.echo(f"\n{payload['suite']} ({payload['kind']}) against {payload['target']}")
    for case in payload["cases"]:
        if case["passed"]:
            continue
        failed = [a["name"] for a in case["assertions"] if not a["passed"] and not a["skipped"]]
        label = f"{case['id']}[{case['attack_id']}]" if case["attack_id"] else case["id"]
        typer.secho(f"  FAIL {label}: {', '.join(failed) or case['error']}", fg=typer.colors.RED)
    if payload["capability_pass_rate"] is not None:
        typer.echo(f"  capability pass rate: {payload['capability_pass_rate']:.1%}")
    if payload["overall_leak_rate"] is not None:
        typer.echo(f"  leak rate: {payload['overall_leak_rate']:.1%}")
        for family, rate in payload["leak_rates"].items():
            typer.echo(f"    {family}: {rate:.1%}")
    typer.echo(
        f"  {counts['passed']}/{counts['cases']} cases passed, "
        f"p50 {payload['latency_p50_ms']}ms, p95 {payload['latency_p95_ms']}ms"
    )
    if counts["skipped_assertions"]:
        typer.echo(f"  {counts['skipped_assertions']} assertions skipped")


if __name__ == "__main__":
    app()
