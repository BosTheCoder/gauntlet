FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.9.17 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/usr/local \
    PORT=8080 \
    GAUNTLET_SUITE_DIR=/app/suites \
    GAUNTLET_DEMO_DELAY_MS=120

WORKDIR /app

COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
RUN uv sync --frozen --no-dev

COPY suites ./suites

EXPOSE 8080
CMD ["sh", "-c", "uvicorn gauntlet.demo.app:app --host 0.0.0.0 --port ${PORT}"]
