#!/usr/bin/env bash
set -euo pipefail

readonly script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

if ! command -v uv >/dev/null 2>&1; then
    printf '%s\n' 'Error: uv is required. Install uv before using this skill.' >&2
    exit 127
fi

exec uv run --script "$script_dir/run_ctfd.py" "$@"
