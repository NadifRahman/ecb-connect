# Security policy

ECBE Connect handles authentication prompts and creates a local network tunnel. Treat every
security report as sensitive.

## Reporting a vulnerability

Use GitHub private vulnerability reporting once the canonical repository is configured. Do not
post credentials, authenticator codes, server transcripts, host keys, or exploit details in a
public issue. Until private reporting is enabled, do not publish a suspected vulnerability; ask
the repository owner for a private contact channel.

## Supported versions

Only the latest beta release receives security fixes. Releases are unsigned until the project
states otherwise. Verify the SHA-256 checksum and GitHub build attestation before running one.

## Security boundaries

- The VNC listener binds only to `127.0.0.1`.
- MFA seeds are never stored.
- ECBE passwords are saved only when explicitly requested and only through the OS keychain.
- RealVNC is not bundled and never receives credentials on its command line.
- Remote `vncconnect` output is parsed as data and is never executed.
- Remote operations load the account's interactive `zsh` login environment, but only fixed,
  validated
  `vncconnect` operations can reach it.
