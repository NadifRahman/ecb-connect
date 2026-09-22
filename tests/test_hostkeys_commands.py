from __future__ import annotations

from pathlib import Path

import asyncssh
import pytest
from keyring.errors import KeyringError

from ecbe_connect.core.errors import CredentialStoreUnavailable
from ecbe_connect.core.ssh_backend import _command_allowed, _login_shell_command
from ecbe_connect.security.credentials import KeyringCredentialStore
from ecbe_connect.security.hostkeys import HostKeyManager


def test_known_host_is_pinned_and_changed_key_is_blocked(tmp_path: Path) -> None:
    manager = HostKeyManager(tmp_path / "known_hosts")
    trusted = asyncssh.generate_private_key("ssh-ed25519").convert_to_public()
    changed = asyncssh.generate_private_key("ssh-ed25519").convert_to_public()
    manager._append("pascal.ecb.torontomu.ca", trusted)
    assert (
        manager._status(
            "pascal.ecb.torontomu.ca", "127.0.0.1", 22, trusted
        )
        == "trusted"
    )
    assert (
        manager._status(
            "pascal.ecb.torontomu.ca", "127.0.0.1", 22, changed
        )
        == "changed"
    )


def test_remote_command_allowlist_blocks_injection() -> None:
    assert _command_allowed("vncconnect")
    assert _command_allowed("vncconnect list")
    assert _command_allowed("vncconnect kill cmp92.ee.ryerson.ca")
    assert not _command_allowed("vncconnect reset")
    assert not _command_allowed("vncconnect kill cmp92; whoami")
    assert not _command_allowed("whoami")


def test_allowlisted_operation_uses_login_environment_as_one_argument() -> None:
    assert _login_shell_command("vncconnect") == "/bin/zsh -lic vncconnect"
    command = _login_shell_command("vncconnect kill cmp92.ee.ryerson.ca")
    assert command == "/bin/zsh -lic 'vncconnect kill cmp92.ee.ryerson.ca'"


def test_keychain_failure_does_not_fall_back_to_plaintext(monkeypatch) -> None:
    def unavailable(service: str, username: str) -> None:
        del service, username
        raise KeyringError("locked")

    monkeypatch.setattr("keyring.get_password", unavailable)
    with pytest.raises(CredentialStoreUnavailable):
        KeyringCredentialStore().get_password("student")
