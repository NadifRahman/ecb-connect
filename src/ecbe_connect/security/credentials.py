from __future__ import annotations

import re

import keyring
from keyring.errors import KeyringError

from ecbe_connect.core.errors import CredentialStoreUnavailable, UserCancelled, ValidationError
from ecbe_connect.core.models import PromptKind
from ecbe_connect.core.protocols import CredentialStore, PromptProvider

_SERVICE_NAME = "ecbe-connect"
_MFA_CODE = re.compile(r"^\d{6}$")


class KeyringCredentialStore(CredentialStore):
    def get_password(self, username: str) -> str | None:
        try:
            return keyring.get_password(_SERVICE_NAME, username)
        except KeyringError as exc:
            raise CredentialStoreUnavailable(
                "The operating-system keychain is unavailable."
            ) from exc

    def set_password(self, username: str, password: str) -> None:
        try:
            keyring.set_password(_SERVICE_NAME, username, password)
        except KeyringError as exc:
            raise CredentialStoreUnavailable(
                "The password was not saved because the operating-system keychain is unavailable."
            ) from exc

    def delete_password(self, username: str) -> None:
        try:
            keyring.delete_password(_SERVICE_NAME, username)
        except keyring.errors.PasswordDeleteError:
            return
        except KeyringError as exc:
            raise CredentialStoreUnavailable("The keychain entry could not be removed.") from exc


class MemoryCredentialStore(CredentialStore):
    def __init__(self) -> None:
        self._values: dict[str, str] = {}

    def get_password(self, username: str) -> str | None:
        return self._values.get(username)

    def set_password(self, username: str, password: str) -> None:
        self._values[username] = password

    def delete_password(self, username: str) -> None:
        self._values.pop(username, None)


class CredentialBroker:
    def __init__(
        self,
        provider: PromptProvider,
        store: CredentialStore,
        username: str,
        *,
        remember_password: bool,
        max_attempts: int = 8,
    ) -> None:
        self.provider = provider
        self.store = store
        self.username = username
        self.remember_password = remember_password
        self.max_attempts = max_attempts
        self._session_password: str | None = None
        self._password_from_store = False
        self._saved_password_rejected = False
        self._vnc_password: str | None = None
        self._counts: dict[PromptKind, int] = {}

    def clear_session(self) -> None:
        self._session_password = None
        self._password_from_store = False
        self._saved_password_rejected = False
        self._vnc_password = None
        self._counts.clear()

    def reject_authentication(self) -> bool:
        """Clear a rejected password and report whether it came from the keychain."""
        saved_password_was_used = self._password_from_store
        self._session_password = None
        self._password_from_store = False
        self._saved_password_rejected = saved_password_was_used
        if saved_password_was_used:
            self.store.delete_password(self.username)
        return saved_password_was_used

    def confirm_authentication(self) -> None:
        """Persist a prompted password only after the server accepts authentication."""
        if (
            self.remember_password
            and self._session_password is not None
            and not self._password_from_store
        ):
            self.store.set_password(self.username, self._session_password)
        self._saved_password_rejected = False

    async def answer(self, kind: PromptKind, prompt: str) -> str:
        count = self._counts.get(kind, 0) + 1
        self._counts[kind] = count
        if count > self.max_attempts:
            raise UserCancelled("Too many authentication attempts; connection stopped.")

        if kind == PromptKind.ECBE_PASSWORD:
            if self._session_password is not None:
                return self._session_password
            if self.remember_password:
                saved = self.store.get_password(self.username)
                if saved:
                    self._session_password = saved
                    self._password_from_store = True
                    return saved
            label = (
                "Saved password was rejected. Enter your ECBE network password"
                if self._saved_password_rejected
                else "ECBE network password"
            )
            value = await self.provider.request_secret(kind, label)
            if not value:
                raise UserCancelled("Password entry was cancelled.")
            self._session_password = value
            self._password_from_store = False
            return value

        if kind == PromptKind.MFA_CODE:
            value = await self.provider.request_secret(kind, "Fresh 6-digit verification code")
            if not _MFA_CODE.fullmatch(value):
                raise ValidationError("The verification code must contain exactly 6 digits.")
            return value

        label = "New VNC password" if kind == PromptKind.VNC_PASSWORD else "Confirm VNC password"
        value = await self.provider.request_secret(kind, label)
        if not value:
            raise UserCancelled("VNC password entry was cancelled.")
        if kind == PromptKind.VNC_PASSWORD:
            self._vnc_password = value
        elif self._vnc_password is not None:
            if value != self._vnc_password:
                self._vnc_password = None
                raise ValidationError("The VNC password confirmation did not match.")
            self._vnc_password = None
        return value
