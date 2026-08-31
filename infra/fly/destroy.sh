#!/usr/bin/env bash
# MANAGED BY demo-tools — DO NOT EDIT. Run `just sync` to update.
set -euo pipefail
APP="bos-gauntlet"
read -r -p "Destroy ${APP}? This removes the Fly app(s) and cert. [y/N] " ans
case "$ans" in
    [yY]|[yY][eE][sS]) ;;
    *) echo "Aborted."; exit 0 ;;
esac
fly apps destroy --yes "$APP" || true
echo "Destroyed."
