#!/bin/bash
# Open the same update dialog as the gear menu.
# Public HTTPS updates do not require a GitHub account.
set -e
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec /bin/bash "$PROJECT_DIR/start_mac.command" --check-updates "$@"
