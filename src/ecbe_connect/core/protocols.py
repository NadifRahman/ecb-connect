from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from ecbe_connect.core.models import AppEvent, PromptKind


class PromptProvider(Protocol):
    async def request_secret(self, kind: PromptKind, message: str) -> str: ...

    async def confirm(self, title: str, message: str) -> bool: ...

    async def choose(self, title: str, choices: Sequence[str]) -> str: ...


class EventSink(Protocol):
    def emit(self, event: AppEvent) -> None: ...


class CredentialStore(Protocol):
    def get_password(self, username: str) -> str | None: ...

    def set_password(self, username: str, password: str) -> None: ...

    def delete_password(self, username: str) -> None: ...


class ViewerLauncher(Protocol):
    def detect(self, configured_path: str | None = None) -> str | None: ...

    def launch(self, address: str, configured_path: str | None = None) -> None: ...

