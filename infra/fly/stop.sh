#!/usr/bin/env bash
# MANAGED BY demo-tools — DO NOT EDIT. Run `just sync` to update.
set -euo pipefail
APP="bos-gauntlet"
fly machines stop --app "$APP" || true
echo "Stopped. Billing on this app is now ~\$0 until 'just start'."
