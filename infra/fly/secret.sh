#!/usr/bin/env bash
# MANAGED BY demo-tools — DO NOT EDIT. Run `just sync` to update.
set -euo pipefail
APP="bos-gauntlet"
KV="${1:-}"
if [[ -z "$KV" ]]; then
    echo "Usage: just secret KEY=VALUE" >&2
    exit 1
fi
fly secrets set --app "$APP" "$KV"
