---
name: ctfd-cli
description: Run the bundled participant-facing CTFd CLI with uv. Use when an agent needs to list or inspect CTFd challenges, view hints or the scoreboard, inspect the current user's solves and submissions, submit a flag, or unlock a hint without installing the ctfd package globally or cloning its repository.
---

# CTFd CLI

Keep the shell in the directory that contains the target CTF's `.env`. Resolve this
skill's directory to an absolute path and invoke its `scripts/ctfd.sh`; do not change
into the skill directory. The wrapper runs the Python package bundled under `scripts/`
with the dependencies declared in `scripts/run_ctfd.py`:

```console
uv run --script /path/to/skill/scripts/run_ctfd.py ...
```

## Configure Access

Set `CTFD_URL`, `CTFD_TOKEN`, and optionally `CTFD_TIMEOUT` in the environment or in
the current directory's `.env`.

Do not print, log, or pass `CTFD_TOKEN` on the command line. Prefer environment or
`.env` configuration so the token does not appear in process listings or shell history.

## Run Commands

Use `--short` before the command for concise, agent-readable output:

```console
/path/to/skill/scripts/ctfd.sh --short challenges list
/path/to/skill/scripts/ctfd.sh --short challenges show 12
/path/to/skill/scripts/ctfd.sh --short scoreboard
/path/to/skill/scripts/ctfd.sh --short me
/path/to/skill/scripts/ctfd.sh --short me solves
/path/to/skill/scripts/ctfd.sh --short me submissions --challenge-id 12
```

Use `--json` instead of `--short` when structured output is required:

```console
/path/to/skill/scripts/ctfd.sh challenges list --json
/path/to/skill/scripts/ctfd.sh challenges show 12 --json
/path/to/skill/scripts/ctfd.sh me submissions --json
```

Forward filters and global connection overrides directly to the CLI. Keep global
options such as `--url`, `--timeout`, and `--short` before the subcommand.

## Mutating Operations

Submit a flag only when the user intends that exact value to be submitted:

```console
/path/to/skill/scripts/ctfd.sh --short challenges submit 12 'flag{example}'
```

Unlock a paid hint only after explicit user confirmation because it can spend CTF
points:

```console
/path/to/skill/scripts/ctfd.sh --short challenges unlock-hint 4
```

Do not retry incorrect submissions automatically.

## Handle Results

Interpret exit codes as follows:

- `0`: success, including a correct or already-solved submission
- `1`: operation-level failure, such as an incorrect submission
- `3`: missing or invalid configuration
- `4`: authentication or permission failure
- `5`: network failure
- `6`: CTFd API response failure

Preserve stdout and stderr when reporting failures, but redact credentials if an
unexpected upstream message contains them.
