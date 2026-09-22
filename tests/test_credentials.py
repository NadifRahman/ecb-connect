from __future__ import annotations

from collections.abc import Sequence

import pytest

from ecbe_connect.core.errors import UserCancelled, ValidationError
from ecbe_connect.core.models import PromptKind
from ecbe_connect.security.credentials import CredentialBroker, MemoryCredentialStore


class Prompts:
    def __init__(self, values: list[str]) -> None:
        self.values = iter(values)
        self.requested: list[PromptKind] = []

    async def request_secret(self, kind: PromptKind, message: str) -> str:
        del message
        self.requested.append(kind)
        return next(self.values)

    async def confirm(self, title: str, message: str) -> bool:
        del title, message
        return True

    async def choose(self, title: str, choices: Sequence[str]) -> str:
        del title
        return choices[0]


@pytest.mark.asyncio
async def test_password_reused_in_session_and_saved_only_when_requested() -> None:
    prompts = Prompts(["ecbe-secret"])
    store = MemoryCredentialStore()
    broker = CredentialBroker(prompts, store, "student", remember_password=True)
    assert await broker.answer(PromptKind.ECBE_PASSWORD, "Password:") == "ecbe-secret"
    assert await broker.answer(PromptKind.ECBE_PASSWORD, "Password:") == "ecbe-secret"
    assert prompts.requested == [PromptKind.ECBE_PASSWORD]
    assert store.get_password("student") == "ecbe-secret"
    broker.clear_session()


@pytest.mark.asyncio
async def test_mfa_is_fresh_and_validated_each_time() -> None:
    prompts = Prompts(["123456", "654321"])
    broker = CredentialBroker(
        prompts, MemoryCredentialStore(), "student", remember_password=False
    )
    assert await broker.answer(PromptKind.MFA_CODE, "Verification code:") == "123456"
    assert await broker.answer(PromptKind.MFA_CODE, "Verification code:") == "654321"
    assert prompts.requested == [PromptKind.MFA_CODE, PromptKind.MFA_CODE]


@pytest.mark.asyncio
async def test_invalid_mfa_and_vnc_confirmation_are_rejected() -> None:
    broker = CredentialBroker(
        Prompts(["not-six"]), MemoryCredentialStore(), "student", remember_password=False
    )
    with pytest.raises(ValidationError):
        await broker.answer(PromptKind.MFA_CODE, "Verification code:")

    broker = CredentialBroker(
        Prompts(["vnc-one", "vnc-two"]),
        MemoryCredentialStore(),
        "student",
        remember_password=False,
    )
    await broker.answer(PromptKind.VNC_PASSWORD, "Password:")
    with pytest.raises(ValidationError):
        await broker.answer(PromptKind.VNC_PASSWORD_CONFIRM, "Verify:")


@pytest.mark.asyncio
async def test_attempts_are_bounded() -> None:
    broker = CredentialBroker(
        Prompts(["111111", "222222", "333333"]),
        MemoryCredentialStore(),
        "student",
        remember_password=False,
        max_attempts=2,
    )
    await broker.answer(PromptKind.MFA_CODE, "Verification code:")
    await broker.answer(PromptKind.MFA_CODE, "Verification code:")
    with pytest.raises(UserCancelled):
        await broker.answer(PromptKind.MFA_CODE, "Verification code:")

