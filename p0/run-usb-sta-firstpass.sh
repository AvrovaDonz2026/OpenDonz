#!/usr/bin/env bash
# Compatibility alias: never maintain a second constraint/failure policy.
set -euo pipefail
exec "$(cd "$(dirname "$0")" && pwd)/run-usb-sta.sh" "$@"
