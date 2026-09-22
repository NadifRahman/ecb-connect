from __future__ import annotations

import pytest

from ecbe_connect.core.errors import ValidationError
from ecbe_connect.core.models import PromptKind, SessionTarget
from ecbe_connect.core.parsing import (
    RemotePromptScanner,
    classify_auth_prompt,
    parse_session_targets,
)


def test_parses_observed_vncconnect_tunnel() -> None:
    output = "ssh -L 127.0.0.1:5900:cmp92.ee.ryerson.ca:5902 user@pascal"
    assert parse_session_targets(output) == [
        SessionTarget(host="cmp92.ee.ryerson.ca", remote_port=5902)
    ]


def test_parses_unique_multiple_sessions() -> None:
    output = "\n".join(
        [
            "127.0.0.1:5900:cmp01.ee.ryerson.ca:5901",
            "127.0.0.1:5900:cmp01.ee.ryerson.ca:5901",
            "127.0.0.1:5900:lab-2.ecb.torontomu.ca:5910",
        ]
    )
    assert parse_session_targets(output) == [
        SessionTarget("cmp01.ee.ryerson.ca", 5901),
        SessionTarget("lab-2.ecb.torontomu.ca", 5910),
    ]


def test_rejects_untrusted_workstation_text() -> None:
    with pytest.raises(ValidationError):
        parse_session_targets("127.0.0.1:5900:attacker.example:5901")


def test_auth_prompt_classification() -> None:
    assert classify_auth_prompt("Password:") == PromptKind.ECBE_PASSWORD
    assert classify_auth_prompt("Verification code:") == PromptKind.MFA_CODE
    assert classify_auth_prompt("unrelated") is None


def test_remote_prompt_scanner_handles_nested_and_vnc_prompts() -> None:
    scanner = RemotePromptScanner()
    assert scanner.feed("Password:") == PromptKind.ECBE_PASSWORD
    assert scanner.feed("Verification code:") == PromptKind.MFA_CODE
    assert scanner.feed("Are you sure you want to continue connecting (yes/no)?") == "host-confirm"
    assert scanner.feed("Create a VNC connection password\nPassword:") == PromptKind.VNC_PASSWORD
    assert scanner.feed("Verify:") == PromptKind.VNC_PASSWORD_CONFIRM

