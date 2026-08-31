"""The web demo.

One page. Pick a suite, hit run, watch cases land one at a time, then flip the sample
agent to its defended variant and watch the leak rate fall to zero.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .agent import SECRET
from .runs import SUITES, RunRecord, get_run, start_run

HERE = Path(__file__).parent
templates = Jinja2Templates(directory=HERE / "templates")


def _fragment(request: Request, record: RunRecord) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "results.html",
        {"run": record, "cases": record.completed, "report": record.report},
    )


def create_app() -> FastAPI:
    app = FastAPI(title="gauntlet demo", docs_url=None, redoc_url=None)
    app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(request, "index.html", {"secret": SECRET})

    @app.post("/runs", response_class=HTMLResponse)
    def create_run(
        request: Request,
        suite: Annotated[str, Form()],
        hardened: Annotated[str | None, Form()] = None,
    ) -> HTMLResponse:
        if suite not in SUITES:
            raise HTTPException(status_code=422, detail=f"unknown suite {suite!r}")
        return _fragment(request, start_run(suite, hardened is not None))

    @app.get("/runs/{run_id}.json")
    def run_json(run_id: str) -> JSONResponse:
        record = get_run(run_id)
        if record is None:
            raise HTTPException(status_code=404, detail="no such run")
        return JSONResponse(
            {
                "id": record.id,
                "suite": record.suite,
                "hardened": record.hardened,
                "total": record.total,
                "done": record.done,
                "report": record.report,
            }
        )

    @app.get("/runs/{run_id}", response_class=HTMLResponse)
    def poll_run(request: Request, run_id: str) -> HTMLResponse:
        record = get_run(run_id)
        if record is None:
            raise HTTPException(status_code=404, detail="no such run")
        return _fragment(request, record)

    return app


app = create_app()
