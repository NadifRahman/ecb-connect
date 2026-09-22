# Contributing

ECBE Connect handles credentials and creates an SSH tunnel into university systems. Keep changes
small, reviewable, and limited to the documented workflow. Do not add unattended authentication,
credential files, workstation scanning, arbitrary remote commands, telemetry, or RealVNC binaries.

## Local checks

Use Python 3.12, create a virtual environment, and install the locked development environment:

```text
python -m pip install uv
uv sync --locked --all-extras
uv run pytest
uv run ruff check src tests scripts
uv run mypy src
uv run bandit -q -r src
uv run pip-audit
```

Pull requests which affect parsing, authentication, host-key trust, forwarding, viewer launch,
logging, or local-data deletion need tests. Never include real usernames, passwords, verification
codes, host fingerprints, home paths, or complete server transcripts in issues and test fixtures.

Before a release, complete the manual platform checklist in
[docs/release-checklist.md](docs/release-checklist.md).

