# Release checklist

This checklist is mandatory for a public beta release.

## Security and policy

- Confirm the README, first-run screen, About page, release notes, and security guide display the
  unofficial-use disclaimer.
- Confirm no TMU or RealVNC logos, fonts, screenshots, or binaries are bundled.
- Review SSH host-key trust, the loopback-only listener, transcript parsing, allowlisted commands,
  viewer arguments, and all logs/diagnostics.
- Run a canary-secret search across configuration, logs, temporary files, exceptions, diagnostics,
  and packaged files.
- Review dependency changes, licenses, vulnerability results, the SBOM, and build provenance.
- Enable private vulnerability reporting in the GitHub repository settings.
- Check whether ECBE or TMU has published a relevant policy or technical change. If they object,
  pause releases and publish a visible notice; do not add a remote kill switch.

## Automated checks

Run tests, Ruff, mypy, Bandit, pip-audit, the build script, and an archive scan on a clean checkout.
Verify the generated SHA-256 file independently.

## Manual platform checks

Test clean installation, viewer detection, first-use host trust, rejected/changed keys, repeated
MFA, existing and multiple sessions, busy port fallback, tray/menu-bar retention, reconnect,
disconnect, app shutdown, network loss, and Clear local data on:

- Windows x64
- macOS Intel
- macOS Apple Silicon
- Linux x64, including one desktop without a usable tray

Unsigned beta packages must clearly explain SmartScreen and Gatekeeper warnings. Do not call a
release stable until Windows signing and macOS signing/notarization are in place.

