# Security and privacy

ECBE Connect is a local SSH/VNC helper, not an official university service. It has no telemetry,
analytics, advertising, cloud account, or project-operated server.

## Data stored locally

- Username, gateway, local-port preference, viewer path, and UI preferences.
- Accepted SSH host keys in an app-specific `known_hosts` file.
- Small rotating logs containing sanitized connection stages and errors.
- The ECBE password only when **Remember password** is selected and a supported OS keychain is
  available.

MFA seeds, MFA codes, VNC passwords, terminal transcripts, remote desktop contents, and coursework
are not stored.

## Network connections

- The configured ECBE gateway for SSH.
- The assigned ECBE workstation, reached only through the gateway tunnel.
- GitHub only when the user manually chooses **Check for updates** after a canonical release URL is
  configured.

The local VNC port is bound only to `127.0.0.1`, not to the local network.

## Important residual risks

- First-use SSH trust is vulnerable if the fingerprint is accepted without independent
  verification.
- An unlocked or compromised computer may expose data available to that user, including keychain
  entries.
- Python and its dependencies cannot guarantee immediate removal of every secret copy from memory
  or operating-system crash dumps.
- Unsigned beta binaries can trigger OS warnings and can be maliciously repackaged. Download only
  from the canonical release page and verify checksums and build attestations.
- A parser or dependency vulnerability could affect credential confidentiality. Releases require
  tests, dependency auditing, and a reviewed lockfile, but no software can eliminate all risk.

## University and third-party rules

Use only your own authorized account. Do not use the app to share access, bypass MFA, scan systems,
or interfere with other users. Review TMU's
[Acceptable Use Policy](https://www.torontomu.ca/policies/policy-list/acceptable-use-policy/)
and [Student Code](https://www.torontomu.ca/senate/policies/student-code-of-non-academic-conduct-policy-61/).

ECBE Connect is published without departmental approval. Its unofficial disclaimer does not grant
permission or override policy. Stop using it if ECBE directs students to do so or if its behavior
differs from current official instructions.

RealVNC is installed and licensed separately. This project does not redistribute it.

## Unofficial-use disclaimer

**Unofficial software — use at your own risk.** ECBE Connect is an independent student project and
is not affiliated with, endorsed by, sponsored by, or supported by Toronto Metropolitan
University, the Department of Electrical, Computer, and Biomedical Engineering, or RealVNC
Limited. Use this software only with an account and systems you are authorized to access, and only
in accordance with applicable university policies and third-party terms. You are responsible for
protecting your credentials, verifying connection details, maintaining backups, and complying with
all applicable rules. The software is provided “as is,” without warranties or guarantees of
availability, security, compatibility, or fitness for a particular purpose. To the maximum extent
permitted by law, the project’s authors and contributors are not liable for account restrictions,
data loss, interrupted work, security incidents, or other damages arising from its use. Stop using
the tool and contact ECBE technical support if its behaviour differs from official instructions.

This disclaimer does not grant authorization, override TMU policy, or guarantee that every
liability limitation is enforceable.
