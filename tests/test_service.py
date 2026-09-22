from __future__ import annotations

import asyncio
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from ecbe_connect.config import AppPaths, ConfigManager
from ecbe_connect.core.models import AppEvent, ConnectionProfile, ConnectionState, PromptKind
from ecbe_connect.core.service import ECBEConnectionService
from ecbe_connect.security.credentials import MemoryCredentialStore


class Prompts:
    async def request_secret(self, kind: PromptKind, message: str) -> str:
        del kind, message
        return "unused"

    async def confirm(self, title: str, message: str) -> bool:
        del title, message
        return True

    async def choose(self, title: str, choices: Sequence[str]) -> str:
        del title
        return choices[-1]


class Events:
    def __init__(self) -> None:
        self.values: list[AppEvent] = []

    def emit(self, event: AppEvent) -> None:
        self.values.append(event)


class Listener:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:
        return None


class Gateway:
    def __init__(self, output: str, busy_ports: set[int] | None = None) -> None:
        self.output = output
        self.busy_ports = busy_ports or set()
        self.commands: list[str] = []
        self.forwarded: list[tuple[int, str, int]] = []
        self.closed = False
        self.close_count = 0
        self._closed = asyncio.Event()

    async def run_vnc_command(self, command: str, **kwargs: Any) -> str:
        del kwargs
        self.commands.append(command)
        return self.output

    async def forward(self, port: int, target: Any) -> Listener:
        if port in self.busy_ports:
            raise OSError("busy")
        self.forwarded.append((port, target.host, target.remote_port))
        return Listener()

    def close(self) -> None:
        self.closed = True
        self.close_count += 1
        self._closed.set()

    def abort(self) -> None:
        self.close()

    async def wait_closed(self) -> None:
        await self._closed.wait()


class Connector:
    def __init__(self, gateway: Gateway) -> None:
        self.gateway = gateway
        self.calls: list[tuple[str, str]] = []

    async def connect(self, host: str, username: str, prompts: Any, broker: Any) -> Gateway:
        del prompts, broker
        self.calls.append((host, username))
        return self.gateway


class Viewer:
    def __init__(self) -> None:
        self.launches: list[tuple[str, str | None]] = []

    def detect(self, configured_path: str | None = None) -> str | None:
        return configured_path or "viewer"

    def launch(self, address: str, configured_path: str | None = None) -> None:
        self.launches.append((address, configured_path))


@pytest.mark.asyncio
async def test_connect_uses_one_gateway_fallback_port_and_explicit_vnc_address() -> None:
    gateway = Gateway(
        "127.0.0.1:5900:cmp92.ee.ryerson.ca:5902",
        busy_ports={5900},
    )
    connector = Connector(gateway)
    viewer = Viewer()
    events = Events()
    service = ECBEConnectionService(
        connector, Prompts(), MemoryCredentialStore(), viewer, events
    )
    info = await service.connect(ConnectionProfile("student"))

    assert connector.calls == [("pascal.ecb.torontomu.ca", "student")]
    assert gateway.commands == ["vncconnect"]
    assert gateway.forwarded == [(5901, "cmp92.ee.ryerson.ca", 5902)]
    assert viewer.launches == [("127.0.0.1::5901", None)]
    assert info.viewer_address == "127.0.0.1::5901"
    assert service.state == ConnectionState.CONNECTED
    await service.disconnect()
    assert gateway.closed
    assert gateway.close_count == 1
    assert service.state == ConnectionState.IDLE


@pytest.mark.asyncio
async def test_repeated_disconnect_is_idempotent() -> None:
    gateway = Gateway("127.0.0.1:5900:cmp92.ee.ryerson.ca:5902")
    service = ECBEConnectionService(
        Connector(gateway), Prompts(), MemoryCredentialStore(), Viewer(), Events()
    )
    await service.connect(ConnectionProfile("student"), launch_viewer=False)
    await asyncio.gather(service.disconnect(), service.disconnect())
    assert service.state == ConnectionState.IDLE
    assert gateway.close_count == 1


@pytest.mark.asyncio
async def test_multiple_sessions_requires_selection() -> None:
    gateway = Gateway(
        "127.0.0.1:5900:cmp01.ee.ryerson.ca:5901\n"
        "127.0.0.1:5900:cmp02.ee.ryerson.ca:5902"
    )
    service = ECBEConnectionService(
        Connector(gateway), Prompts(), MemoryCredentialStore(), Viewer(), Events()
    )
    info = await service.connect(ConnectionProfile("student"), launch_viewer=False)
    assert info.target.host == "cmp02.ee.ryerson.ca"
    await service.disconnect()


@pytest.mark.asyncio
async def test_clear_local_data_removes_saved_password(tmp_path: Path) -> None:
    store = MemoryCredentialStore()
    store.set_password("student", "secret")
    gateway = Gateway("127.0.0.1:5900:cmp01.ee.ryerson.ca:5901")
    service = ECBEConnectionService(Connector(gateway), Prompts(), store, Viewer(), Events())
    manager = ConfigManager(
        AppPaths(tmp_path / "config", tmp_path / "cache", tmp_path / "logs")
    )
    manager.save(manager.load())
    await service.clear_local_data(manager, "student")
    assert store.get_password("student") is None
    assert not manager.paths.config_file.exists()
