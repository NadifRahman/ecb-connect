from __future__ import annotations

import asyncio
import os
import socket
from pathlib import Path

import asyncssh

from ecbe_connect.core.errors import HostKeyChanged, HostKeyUnknown
from ecbe_connect.core.protocols import PromptProvider


class HostKeyManager:
    def __init__(self, path: Path) -> None:
        self.path = path

    async def ensure_trusted(self, host: str, port: int, prompts: PromptProvider) -> None:
        key = await asyncssh.get_server_host_key(host, port, config=None)
        if key is None:
            raise HostKeyUnknown("The gateway did not provide an SSH host key.")

        loop = asyncio.get_running_loop()
        addresses = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        addr = str(addresses[0][4][0]) if addresses else host
        status = self._status(host, addr, port, key)
        fingerprint = key.get_fingerprint("sha256")

        if status == "trusted":
            return
        if status == "changed":
            raise HostKeyChanged(
                "The ECBE gateway host key changed. Stop and verify the new fingerprint "
                "with ECBE technical support before connecting."
            )
        if status == "revoked":
            raise HostKeyChanged("The ECBE gateway presented a revoked SSH host key.")

        accepted = await prompts.confirm(
            "Trust ECBE gateway?",
            f"First connection to {host}. Verify this fingerprint with ECBE support:\n\n"
            f"{fingerprint}\n\nTrust and save this key?",
        )
        if not accepted:
            raise HostKeyUnknown("The gateway host key was not trusted.")
        self._append(host, key)

    def _status(self, host: str, addr: str, port: int, key: asyncssh.SSHKey) -> str:
        if not self.path.exists() or self.path.stat().st_size == 0:
            return "unknown"
        try:
            known = asyncssh.read_known_hosts(str(self.path))
            host_keys, _ca, revoked, _certs, revoked_certs, _subjects, _revoked_subjects = (
                known.match(host, addr, port)
            )
        except (OSError, ValueError, asyncssh.KeyImportError) as exc:
            raise HostKeyChanged("The saved SSH host-key file is invalid.") from exc
        if any(key == item for item in (*revoked, *revoked_certs)):
            return "revoked"
        if any(key == item for item in host_keys):
            return "trusted"
        if host_keys:
            return "changed"
        return "unknown"

    def _append(self, host: str, key: asyncssh.SSHKey) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        exported = key.export_public_key("openssh").decode("ascii").strip()
        with self.path.open("a", encoding="ascii", newline="\n") as stream:
            stream.write(f"{host} {exported}\n")
        if os.name != "nt":
            self.path.chmod(0o600)
