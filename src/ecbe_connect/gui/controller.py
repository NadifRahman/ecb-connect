from __future__ import annotations

import asyncio
import concurrent.futures
import threading
from collections.abc import Coroutine, Sequence
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QObject, Signal

from ecbe_connect.config import ConfigManager
from ecbe_connect.core.diagnostics import run_diagnostics
from ecbe_connect.core.models import AppEvent, ConnectionInfo, ConnectionProfile, PromptKind
from ecbe_connect.core.protocols import EventSink, PromptProvider
from ecbe_connect.runtime import build_service


@dataclass(slots=True)
class PromptRequest:
    mode: str
    title: str
    message: str
    choices: Sequence[str]
    future: concurrent.futures.Future[Any]


class QtPromptProvider(PromptProvider):
    def __init__(self, signal: Any) -> None:
        self.signal = signal

    async def request_secret(self, kind: PromptKind, message: str) -> str:
        future: concurrent.futures.Future[str] = concurrent.futures.Future()
        self.signal.emit(PromptRequest("secret", kind.value, message, (), future))
        return await asyncio.wrap_future(future)

    async def confirm(self, title: str, message: str) -> bool:
        future: concurrent.futures.Future[bool] = concurrent.futures.Future()
        self.signal.emit(PromptRequest("confirm", title, message, (), future))
        return await asyncio.wrap_future(future)

    async def choose(self, title: str, choices: Sequence[str]) -> str:
        future: concurrent.futures.Future[str] = concurrent.futures.Future()
        self.signal.emit(PromptRequest("choose", title, "", choices, future))
        return await asyncio.wrap_future(future)


class QtEventSink(EventSink):
    def __init__(self, signal: Any) -> None:
        self.signal = signal

    def emit(self, event: AppEvent) -> None:
        self.signal.emit(event)


class CoreController(QObject):
    event_received = Signal(object)
    prompt_requested = Signal(object)
    operation_result = Signal(str, object)
    operation_failed = Signal(str, str)
    connected_changed = Signal(bool, object)

    def __init__(self, config: ConfigManager) -> None:
        super().__init__()
        self.config = config
        self.loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, name="ecbe-core", daemon=False)
        self._thread.start()
        self.prompts = QtPromptProvider(self.prompt_requested)
        self.events = QtEventSink(self.event_received)
        self.service = build_service(self.prompts, self.events, config)

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def start_connection(self, profile: ConnectionProfile, launch_viewer: bool = True) -> None:
        async def operation() -> ConnectionInfo:
            return await self.service.connect(profile, launch_viewer=launch_viewer)

        self._submit("connect", operation(), connected=True)

    def stop_connection(self) -> None:
        self._submit("disconnect", self.service.disconnect(), connected=False)

    def reconnect(self, profile: ConnectionProfile) -> None:
        async def operation() -> ConnectionInfo:
            await self.service.disconnect()
            return await self.service.connect(profile, launch_viewer=True)

        self._submit("reconnect", operation(), connected=True)

    def list_sessions(self, profile: ConnectionProfile) -> None:
        self._submit("sessions", self.service.list_sessions(profile))

    def change_vnc_password(self, profile: ConnectionProfile) -> None:
        self._submit("passwd", self.service.change_vnc_password(profile))

    def kill_session(self, profile: ConnectionProfile, host: str) -> None:
        self._submit("kill", self.service.kill_session(profile, host))

    def diagnostics(self, profile: ConnectionProfile) -> None:
        self._submit(
            "doctor",
            run_diagnostics(
                profile.gateway,
                profile.local_port,
                str(profile.viewer_path) if profile.viewer_path else None,
            ),
        )

    def clear_data(self, username: str) -> None:
        self._submit("clear-data", self.service.clear_local_data(self.config, username))

    def _submit(
        self,
        name: str,
        coroutine: Coroutine[Any, Any, Any],
        *,
        connected: bool | None = None,
    ) -> None:
        future = asyncio.run_coroutine_threadsafe(coroutine, self.loop)

        def finished(result_future: concurrent.futures.Future[Any]) -> None:
            try:
                result = result_future.result()
            except BaseException as exc:
                self.operation_failed.emit(name, str(exc) or "Operation failed.")
                if connected is True:
                    self.connected_changed.emit(False, None)
                return
            self.operation_result.emit(name, result)
            if connected is not None:
                self.connected_changed.emit(connected, result)

        future.add_done_callback(finished)

    def shutdown(self) -> None:
        if not self.loop.is_running():
            return
        future = asyncio.run_coroutine_threadsafe(self.service.disconnect(), self.loop)
        try:
            future.result(timeout=10)
        except Exception as exc:
            self.operation_failed.emit("shutdown", str(exc) or "Shutdown did not finish cleanly.")
        self.loop.call_soon_threadsafe(self.loop.stop)
        self._thread.join(timeout=5)
