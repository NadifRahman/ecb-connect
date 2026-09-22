from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class ConnectionState(StrEnum):
    IDLE = "idle"
    AUTHENTICATING = "authenticating"
    PREPARING_SESSION = "preparing_session"
    OPENING_TUNNEL = "opening_tunnel"
    LAUNCHING_VIEWER = "launching_viewer"
    CONNECTED = "connected"
    DISCONNECTING = "disconnecting"
    FAILED = "failed"


class PromptKind(StrEnum):
    ECBE_PASSWORD = "ecbe_password"  # nosec B105  # noqa: S105 - identifier only
    MFA_CODE = "mfa_code"
    VNC_PASSWORD = "vnc_password"  # nosec B105  # noqa: S105 - identifier only
    VNC_PASSWORD_CONFIRM = "vnc_password_confirm"  # nosec B105  # noqa: S105


class EventLevel(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class ConnectionProfile:
    username: str
    gateway: str = "pascal.ecb.torontomu.ca"
    local_port: int = 5900
    viewer_path: Path | None = None
    remember_password: bool = False


@dataclass(frozen=True, slots=True)
class SessionTarget:
    host: str
    remote_port: int

    @property
    def label(self) -> str:
        return f"{self.host}:{self.remote_port}"


@dataclass(frozen=True, slots=True)
class ConnectionInfo:
    target: SessionTarget
    local_port: int

    @property
    def viewer_address(self) -> str:
        return f"127.0.0.1::{self.local_port}"

    @property
    def uri_address(self) -> str:
        return f"127.0.0.1:{self.local_port}"


@dataclass(frozen=True, slots=True)
class AppEvent:
    code: str
    message: str
    state: ConnectionState
    level: EventLevel = EventLevel.INFO


@dataclass(frozen=True, slots=True)
class DiagnosticCheck:
    name: str
    ok: bool
    detail: str
