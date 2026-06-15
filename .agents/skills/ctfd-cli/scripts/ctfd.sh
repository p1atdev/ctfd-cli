#!/usr/bin/env bash
set -euo pipefail

readonly default_source='git+https://github.com/p1atdev/ctfd-cli.git'
readonly source_spec="${CTFD_CLI_SOURCE:-$default_source}"

if ! command -v uvx >/dev/null 2>&1; then
    printf '%s\n' 'Error: uvx is required. Install uv before using this skill.' >&2
    exit 127
fi

exec uvx --from "$source_spec" ctfd "$@"
