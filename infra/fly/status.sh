#!/usr/bin/env bash
# MANAGED BY demo-tools — DO NOT EDIT. Run `just sync` to update.
set -euo pipefail
APP="bos-gauntlet"
HOSTNAMES=("gauntlet.demos.buildwithbos.com")
fly status --app "$APP"
echo
echo "URLs:"
echo "  https://${APP}.fly.dev"
for host in ${HOSTNAMES[@]+"${HOSTNAMES[@]}"}; do
    echo "  https://${host}"
done
