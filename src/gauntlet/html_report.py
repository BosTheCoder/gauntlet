"""Render a report dict as one self-contained HTML file.

Self-contained is a requirement, not a nicety: the report gets attached to CI runs and
emailed around, and it has to render with no network and no adjacent asset directory.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

_ENV = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "templates"),
    autoescape=select_autoescape(["html", "j2"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.0f}%"


def _tool_calls(calls: list[dict[str, Any]]) -> str:
    return "\n".join(f"{c['name']}({json.dumps(c.get('arguments', {}))})" for c in calls)


def render_html(report: dict[str, Any]) -> str:
    template = _ENV.get_template("report.html.j2")
    return template.render(report=report, pct=_pct, tool_calls=_tool_calls)


def write_html(report: dict[str, Any], path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_html(report))
