#!/usr/bin/env bash
# MANAGED BY demo-tools — DO NOT EDIT. Run `just sync` to update.
set -euo pipefail
echo "db-create is not applicable for stack 'fastapi' (no DB by default)." >&2
echo "Edit the Dockerfile and infra/fly/db-create.sh if you want to add one." >&2
exit 1
