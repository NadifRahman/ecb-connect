from __future__ import annotations

from ecbe_connect.core.errors import ECBEConnectError
from ecbe_connect.core.models import ConnectionState

_ALLOWED: dict[ConnectionState, set[ConnectionState]] = {
    ConnectionState.IDLE: {ConnectionState.AUTHENTICATING},
    ConnectionState.AUTHENTICATING: {
        ConnectionState.PREPARING_SESSION,
        ConnectionState.FAILED,
        ConnectionState.DISCONNECTING,
    },
    ConnectionState.PREPARING_SESSION: {
        ConnectionState.OPENING_TUNNEL,
        ConnectionState.FAILED,
        ConnectionState.DISCONNECTING,
    },
    ConnectionState.OPENING_TUNNEL: {
        ConnectionState.LAUNCHING_VIEWER,
        ConnectionState.CONNECTED,
        ConnectionState.FAILED,
        ConnectionState.DISCONNECTING,
    },
    ConnectionState.LAUNCHING_VIEWER: {
        ConnectionState.CONNECTED,
        ConnectionState.FAILED,
        ConnectionState.DISCONNECTING,
    },
    ConnectionState.CONNECTED: {ConnectionState.DISCONNECTING, ConnectionState.FAILED},
    ConnectionState.DISCONNECTING: {ConnectionState.IDLE, ConnectionState.FAILED},
    ConnectionState.FAILED: {ConnectionState.IDLE, ConnectionState.AUTHENTICATING},
}


class InvalidStateTransition(ECBEConnectError):
    pass


class ConnectionStateMachine:
    def __init__(self) -> None:
        self._state = ConnectionState.IDLE

    @property
    def state(self) -> ConnectionState:
        return self._state

    def transition(self, target: ConnectionState) -> None:
        if target == self._state:
            return
        if target not in _ALLOWED[self._state]:
            raise InvalidStateTransition(f"Cannot move from {self._state} to {target}.")
        self._state = target

    def recover(self) -> None:
        if self._state == ConnectionState.FAILED:
            self.transition(ConnectionState.IDLE)
