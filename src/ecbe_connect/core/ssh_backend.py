from __future__ import annotations

import asyncio
import shlex
from collections.abc import Sequence
from dataclasses import dataclass

import asyncssh

from ecbe_connect.core.errors import AuthenticationFailed, RemoteOutputError, UserCancelled
from ecbe_connect.core.models import PromptKind, SessionTarget
from ecbe_connect.core.parsing import RemotePromptScanner, classify_auth_prompt
from ecbe_connect.core.protocols import PromptProvider
from ecbe_connect.core.validation import validate_workstation
from ecbe_connect.security.credentials import CredentialBroker
from ecbe_connect.security.hostkeys import HostKeyManager

_MAX_TRANSCRIPT = 1_000_000


class _ECBEClient(asyncssh.SSHClient):
    def __init__(self, broker: CredentialBroker) -> None:
        self.broker = broker

    async def password_auth_requested(self) -> str | None:
        return await self.broker.answer(PromptKind.ECBE_PASSWORD, "Password:")

    async def kbdint_auth_requested(self) -> str | None:
        return ""

    async def kbdint_challenge_received(
        self,
        name: str,
        instructions: str,
        lang: str,
        prompts: Sequence[tuple[str, bool]],
    ) -> list[str] | None:
        del name, instructions, lang
        answers: list[str] = []
        for prompt, _echo in prompts:
            kind = classify_auth_prompt(prompt)
            if kind is None:
                return None
            answers.append(await self.broker.answer(kind, prompt))
        return answers


@dataclass(slots=True)
class SSHGateway:
    connection: asyncssh.SSHClientConnection
    prompts: PromptProvider
    broker: CredentialBroker

    async def run_vnc_command(self, command: str, *, vnc_password_command: bool = False) -> str:
        remote_command = _login_shell_command(command)
        process = await self.connection.create_process(
            remote_command,
            term_type="xterm",
            encoding="utf-8",
            stderr=asyncssh.STDOUT,
        )
        scanner = RemotePromptScanner(vnc_password_command=vnc_password_command)
        output: list[str] = []
        length = 0
        try:
            async with asyncio.timeout(600):
                while True:
                    char = await process.stdout.read(1)
                    if not char:
                        break
                    length += len(char)
                    if length > _MAX_TRANSCRIPT:
                        process.terminate()
                        raise RemoteOutputError("The remote command produced too much output.")
                    output.append(char)
                    prompt = scanner.feed(char)
                    if prompt == "host-confirm":
                        accepted = await self.prompts.confirm(
                            "Trust remote workstation?",
                            "The ECBE gateway asked to trust a workstation host key. "
                            "Continue only if this was expected.",
                        )
                        if not accepted:
                            process.terminate()
                            raise UserCancelled("Remote workstation trust was cancelled.")
                        process.stdin.write("yes\n")
                    elif isinstance(prompt, PromptKind):
                        answer = await self.broker.answer(prompt, prompt.value)
                        process.stdin.write(answer + "\n")
                await process.wait()
        except TimeoutError as exc:
            process.terminate()
            raise RemoteOutputError(
                "The remote command timed out while waiting for a response."
            ) from exc
        transcript = "".join(output)
        if "command not found" in transcript.lower():
            raise RemoteOutputError(
                "Pascal did not expose vncconnect in the login environment. "
                "Stop retrying and use the manual guide or contact ECBE support."
            )
        if process.exit_status not in (0, None):
            raise RemoteOutputError(
                f"The ECBE command failed with exit status {process.exit_status}."
            )
        return transcript

    async def forward(self, local_port: int, target: SessionTarget) -> asyncssh.SSHListener:
        return await self.connection.forward_local_port(
            "127.0.0.1", local_port, target.host, target.remote_port
        )

    def close(self) -> None:
        self.connection.close()

    def abort(self) -> None:
        self.connection.abort()

    async def wait_closed(self) -> None:
        await self.connection.wait_closed()


class GatewayConnector:
    def __init__(self, host_keys: HostKeyManager) -> None:
        self.host_keys = host_keys

    async def connect(
        self,
        host: str,
        username: str,
        prompts: PromptProvider,
        broker: CredentialBroker,
    ) -> SSHGateway:
        await self.host_keys.ensure_trusted(host, 22, prompts)
        retried_saved_password = False
        while True:
            try:
                connection = await asyncssh.connect(
                    host,
                    port=22,
                    username=username,
                    client_factory=lambda: _ECBEClient(broker),
                    known_hosts=str(self.host_keys.path),
                    preferred_auth=("keyboard-interactive", "password"),
                    client_keys=[],
                    agent_path=None,
                    config=None,
                    keepalive_interval=30,
                    keepalive_count_max=3,
                    login_timeout=90,
                )
            except asyncssh.PermissionDenied as exc:
                used_saved_password = broker.reject_authentication()
                if used_saved_password and not retried_saved_password:
                    retried_saved_password = True
                    continue
                raise AuthenticationFailed("ECBE authentication was rejected.") from exc
            except (asyncssh.Error, OSError) as exc:
                raise AuthenticationFailed(
                    "Could not establish a secure connection to ECBE."
                ) from exc
            broker.confirm_authentication()
            return SSHGateway(connection=connection, prompts=prompts, broker=broker)


def _command_allowed(command: str) -> bool:
    if command in {"vncconnect", "vncconnect list", "vncconnect passwd"}:
        return True
    if command.startswith("vncconnect kill "):
        host = command.removeprefix("vncconnect kill ")
        try:
            return validate_workstation(host) == host.lower().rstrip(".")
        except Exception:
            return False
    return False


def _login_shell_command(command: str) -> str:
    if not _command_allowed(command):
        raise RemoteOutputError("Blocked an unsupported remote command.")
    # Current ECBE accounts use zsh and expose vncconnect in its interactive login setup. The
    # operation is
    # allowlisted before it is quoted as one fixed -c argument; server output is never run.
    return f"/bin/zsh -lic {shlex.quote(command)}"
