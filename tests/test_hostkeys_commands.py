from __future__ import annotations

from pathlib import Path

import asyncssh
import pytest
from keyring.errors import KeyringError

from ecbe_connect.core.errors import CredentialStoreUnavailable
from ecbe_connect.core.models import PromptKind
from ecbe_connect.core.ssh_backend import GatewayConnector, _command_allowed, _login_shell_command
from ecbe_connect.security.credentials import (
    CredentialBroker,
    KeyringCredentialStore,
    MemoryCredentialStore,
)
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


@pytest.mark.asyncio
async def test_gateway_retries_once_with_prompt_when_saved_password_is_rejected(
    monkeypatch, tmp_path: Path
) -> None:
    class TrustedHostKeys:
        path = tmp_path / "known_hosts"

        async def ensure_trusted(self, host: str, port: int, prompts: object) -> None:
            del host, port, prompts

    class Prompts:
        def __init__(self) -> None:
            self.requests: list[tuple[PromptKind, str]] = []

        async def request_secret(self, kind: PromptKind, message: str) -> str:
            self.requests.append((kind, message))
            return "correct-password"

    attempts: list[str | None] = []

    async def connect(*args, client_factory, **kwargs):
        del args, kwargs
        client = client_factory()
        attempts.append(await client.password_auth_requested())
        if len(attempts) == 1:
            raise asyncssh.PermissionDenied("rejected")
        return object()

    monkeypatch.setattr(asyncssh, "connect", connect)
    prompts = Prompts()
    store = MemoryCredentialStore()
    store.set_password("student", "stale-password")
    broker = CredentialBroker(prompts, store, "student", remember_password=True)

    gateway = await GatewayConnector(TrustedHostKeys()).connect(  # type: ignore[arg-type]
        "pascal.ecb.torontomu.ca", "student", prompts, broker  # type: ignore[arg-type]
    )

    assert gateway.connection is not None
    assert attempts == ["stale-password", "correct-password"]
    assert prompts.requests == [
        (
            PromptKind.ECBE_PASSWORD,
            "Saved password was rejected. Enter your ECBE network password",
        )
    ]
    assert store.get_password("student") == "correct-password"
