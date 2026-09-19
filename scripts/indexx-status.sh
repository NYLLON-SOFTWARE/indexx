#!/usr/bin/env bash
# Read-only validator. Usage: bash scripts/indexx-status.sh [ROOT] [--json]
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
LIBRARY_ROOT="."
if [[ $# -gt 0 && "$1" != --* ]]; then
  LIBRARY_ROOT="$1"
  shift
fi
exec python3 "$SCRIPT_DIR/indexx_status.py" --root "$LIBRARY_ROOT" "$@"
