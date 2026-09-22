from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncssh

from ecbe_connect.config import ConfigManager
from ecbe_connect.core.errors import (
    ConnectionAlreadyActive,
    ECBEConnectError,
    RemoteOutputError,
    ValidationError,
    ViewerNotFound,
)
from ecbe_connect.core.models import (
    AppEvent,
    ConnectionInfo,
    ConnectionProfile,
    ConnectionState,
    EventLevel,
    SessionTarget,
)
from ecbe_connect.core.parsing import parse_session_targets
from ecbe_connect.core.protocols import CredentialStore, EventSink, PromptProvider, ViewerLauncher
from ecbe_connect.core.ssh_backend import GatewayConnector, SSHGateway
from ecbe_connect.core.state import ConnectionStateMachine
from ecbe_connect.core.validation import validate_profile, validate_workstation
from ecbe_connect.security.credentials import CredentialBroker

_MONITOR_CLOSE_TIMEOUT = 1.0
_LISTENER_CLOSE_TIMEOUT = 3.0
_GATEWAY_CLOSE_TIMEOUT = 3.0
_GATEWAY_ABORT_TIMEOUT = 1.0


class NullEventSink:
    def emit(self, event: AppEvent) -> None:
        del event


class ECBEConnectionService:
    def __init__(
        self,
        connector: GatewayConnector,
        prompts: PromptProvider,
        credentials: CredentialStore,
        viewer: ViewerLauncher,
        events: EventSink | None = None,
    ) -> None:
        self.connector = connector
        self.prompts = prompts
        self.credentials = credentials
        self.viewer = viewer
        self.events = events or NullEventSink()
        self.machine = ConnectionStateMachine()
        self.info: ConnectionInfo | None = None
        self._gateway: SSHGateway | None = None
        self._listener: asyncssh.SSHListener | None = None
        self._broker: CredentialBroker | None = None
        self._profile: ConnectionProfile | None = None
        self._monitor: asyncio.Task[None] | None = None
        self._disconnect_lock = asyncio.Lock()
        self._disconnected = asyncio.Event()
        self._disconnected.set()

    @property
    def state(self) -> ConnectionState:
        return self.machine.state

    async def connect(
        self,
        profile: ConnectionProfile,
        *,
        launch_viewer: bool = True,
    ) -> ConnectionInfo:
        if self.state not in {ConnectionState.IDLE, ConnectionState.FAILED}:
            raise ConnectionAlreadyActive("A connection attempt or tunnel is already active.")
        if self.state == ConnectionState.FAILED:
            self.machine.recover()
        profile = validate_profile(profile)
        self._profile = profile
        self._disconnected.clear()
        self._broker = CredentialBroker(
            self.prompts,
            self.credentials,
            profile.username,
            remember_password=profile.remember_password,
        )
        try:
            self._transition(
                ConnectionState.AUTHENTICATING,
                "authenticating",
                "Waiting for ECBE authentication.",
            )
            self._gateway = await self.connector.connect(
                profile.gateway, profile.username, self.prompts, self._broker
            )
            self._transition(
                ConnectionState.PREPARING_SESSION,
                "preparing_session",
                "Finding or starting an ECBE VNC session.",
            )
            output = await self._gateway.run_vnc_command("vncconnect")
            targets = parse_session_targets(output)
            if not targets:
                raise RemoteOutputError(
                    "ECBE did not return a usable VNC tunnel. "
                    "Run Diagnostics or use the manual guide."
                )
            target = await self._select_target(targets)
            self._transition(
                ConnectionState.OPENING_TUNNEL,
                "opening_tunnel",
                "Opening a private local VNC tunnel.",
            )
            local_port, listener = await self._open_listener(profile.local_port, target)
            self._listener = listener
            self.info = ConnectionInfo(target=target, local_port=local_port)

            if launch_viewer:
                self._transition(
                    ConnectionState.LAUNCHING_VIEWER,
                    "launching_viewer",
                    "Opening the installed VNC viewer.",
                )
                try:
                    self.viewer.launch(
                        self.info.viewer_address,
                        str(profile.viewer_path) if profile.viewer_path else None,
                    )
                except ViewerNotFound as exc:
                    self._emit("viewer_missing", str(exc), EventLevel.WARNING)

            self._transition(
                ConnectionState.CONNECTED,
                "connected",
                f"Connected. VNC is available at {self.info.viewer_address}.",
            )
            self._monitor = asyncio.create_task(self._monitor_gateway())
            return self.info
        except Exception as exc:
            await self._cleanup()
            if self.state != ConnectionState.FAILED:
                try:
                    self.machine.transition(ConnectionState.FAILED)
                except ECBEConnectError:
                    pass
            message = (
                str(exc)
                if isinstance(exc, ECBEConnectError)
                else "Connection failed unexpectedly."
            )
            self._emit("connection_failed", message, EventLevel.ERROR)
            self._disconnected.set()
            raise

    async def disconnect(self) -> None:
        async with self._disconnect_lock:
            await self._disconnect_once()

    async def _disconnect_once(self) -> None:
        if self.state == ConnectionState.IDLE:
            return
        if self.state == ConnectionState.FAILED:
            await self._cleanup()
            self.machine.recover()
            self._disconnected.set()
            self._emit("idle", "Disconnected.")
            return
        self._transition(
            ConnectionState.DISCONNECTING,
            "disconnecting",
            "Closing the VNC tunnel.",
        )
        await self._cleanup()
        self.machine.transition(ConnectionState.IDLE)
        self._disconnected.set()
        self._emit("idle", "Disconnected.")

    async def wait_until_disconnected(self) -> None:
        await self._disconnected.wait()

    async def list_sessions(self, profile: ConnectionProfile) -> list[SessionTarget]:
        async with self._operation_gateway(profile) as gateway:
            output = await gateway.run_vnc_command("vncconnect list")
            return parse_session_targets(output)

    async def change_vnc_password(self, profile: ConnectionProfile) -> None:
        async with self._operation_gateway(profile) as gateway:
            await gateway.run_vnc_command("vncconnect passwd", vnc_password_command=True)
        self._emit("vnc_password_changed", "VNC password updated.")

    async def kill_session(self, profile: ConnectionProfile, host: str) -> None:
        safe_host = validate_workstation(host)
        async with self._operation_gateway(profile) as gateway:
            await gateway.run_vnc_command(f"vncconnect kill {safe_host}")
        self._emit("session_killed", "The selected VNC session was stopped.")

    async def clear_local_data(self, config: ConfigManager, username: str) -> None:
        await self.disconnect()
        if username:
            self.credentials.delete_password(username)
        from ecbe_connect.logging_setup import close_logging

        close_logging()
        config.clear_files()
        self._emit(
            "local_data_cleared",
            "Local settings, logs, host keys, and saved password removed.",
        )

    async def _select_target(self, targets: list[SessionTarget]) -> SessionTarget:
        if len(targets) == 1:
            return targets[0]
        labels = [target.label for target in targets]
        selected = await self.prompts.choose("Choose an existing VNC session", labels)
        for target in targets:
            if target.label == selected:
                return target
        raise ValidationError("No VNC session was selected.")

    async def _open_listener(
        self, preferred_port: int, target: SessionTarget
    ) -> tuple[int, asyncssh.SSHListener]:
        if self._gateway is None:
            raise RemoteOutputError("The SSH gateway connection is unavailable.")
        for port in range(preferred_port, min(preferred_port + 50, 65536)):
            try:
                listener = await self._gateway.forward(port, target)
                return port, listener
            except OSError:
                continue
        raise RemoteOutputError("No available local VNC port was found.")

    @asynccontextmanager
    async def _operation_gateway(
        self, profile: ConnectionProfile
    ) -> AsyncIterator[SSHGateway]:
        profile = validate_profile(profile)
        if self._gateway is not None and self._profile == profile:
            yield self._gateway
            return
        broker = CredentialBroker(
            self.prompts,
            self.credentials,
            profile.username,
            remember_password=profile.remember_password,
        )
        gateway = await self.connector.connect(
            profile.gateway, profile.username, self.prompts, broker
        )
        try:
            yield gateway
        finally:
            gateway.close()
            await gateway.wait_closed()
            broker.clear_session()

    async def _monitor_gateway(self) -> None:
        gateway = self._gateway
        if gateway is None:
            return
        try:
            await gateway.wait_closed()
            if self.state == ConnectionState.CONNECTED:
                if self._listener is not None:
                    self._listener.close()
                    self._listener = None
                self.machine.transition(ConnectionState.FAILED)
                self._emit(
                    "connection_lost",
                    "The ECBE connection closed. Reconnect to restore VNC.",
                    EventLevel.ERROR,
                )
                self._disconnected.set()
        except asyncio.CancelledError:
            return

    async def _cleanup(self) -> None:
        current = asyncio.current_task()
        if self._monitor is not None and self._monitor is not current:
            monitor = self._monitor
            monitor.cancel()
            try:
                await asyncio.wait_for(monitor, timeout=_MONITOR_CLOSE_TIMEOUT)
            except (TimeoutError, asyncio.CancelledError):
                pass
        self._monitor = None
        if self._listener is not None:
            listener = self._listener
            self._listener = None
            listener.close()
            try:
                await asyncio.wait_for(
                    listener.wait_closed(), timeout=_LISTENER_CLOSE_TIMEOUT
                )
            except TimeoutError:
                self._emit(
                    "listener_close_timeout",
                    "The local VNC listener did not confirm shutdown; continuing cleanup.",
                    EventLevel.WARNING,
                )
        if self._gateway is not None:
            gateway = self._gateway
            self._gateway = None
            gateway.close()
            try:
                await asyncio.wait_for(
                    gateway.wait_closed(), timeout=_GATEWAY_CLOSE_TIMEOUT
                )
            except TimeoutError:
                gateway.abort()
                try:
                    await asyncio.wait_for(
                        gateway.wait_closed(), timeout=_GATEWAY_ABORT_TIMEOUT
                    )
                except TimeoutError:
                    self._emit(
                        "gateway_close_timeout",
                        "The SSH connection was forcibly abandoned during shutdown.",
                        EventLevel.WARNING,
                    )
        if self._broker is not None:
            self._broker.clear_session()
            self._broker = None
        self.info = None

    def _transition(self, state: ConnectionState, code: str, message: str) -> None:
        self.machine.transition(state)
        self._emit(code, message)

    def _emit(self, code: str, message: str, level: EventLevel = EventLevel.INFO) -> None:
        self.events.emit(AppEvent(code=code, message=message, state=self.state, level=level))
