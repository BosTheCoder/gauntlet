# Lint, typecheck and test. The one command CI runs.
check: lint typecheck test

test:
    uv run pytest

lint:
    uv run ruff format --check .
    uv run ruff check .

typecheck:
    uv run pyright

fmt:
    uv run ruff format .
    uv run ruff check --fix .

# Run a suite against the bundled sample agent. `just eval safety defended`
eval suite="safety" mode="vulnerable":
    uv run gauntlet run suites/{{suite}}.yaml \
        --target python:gauntlet.demo.agent:{{mode}} \
        --report out/{{suite}}-{{mode}}.json \
        --html out/{{suite}}-{{mode}}.html

# Regenerate the committed baselines the CI gate compares against.
baselines:
    uv run gauntlet run suites/capability.yaml --target python:gauntlet.demo.agent:defended \
        --report baselines/capability.json
    uv run gauntlet run suites/safety.yaml --target python:gauntlet.demo.agent:defended \
        --report baselines/safety.json

# The web demo on http://localhost:8080
demo port="8080":
    GAUNTLET_DEMO_DELAY_MS=120 uv run uvicorn gauntlet.demo.app:app --reload \
        --host 127.0.0.1 --port {{port}}

deploy:
    flyctl deploy
