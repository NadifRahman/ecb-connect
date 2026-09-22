from __future__ import annotations

import re

from ecbe_connect.core.models import PromptKind, SessionTarget
from ecbe_connect.core.validation import validate_port, validate_workstation

_TUNNEL = re.compile(
    r"127\.0\.0\.1:(?P<local>\d{1,5}):"
    r"(?P<host>[A-Za-z0-9.-]+):(?P<remote>\d{1,5})"
)
_MFA_PROMPT = re.compile(r"Verification\s+code:\s*$", re.IGNORECASE)
_VERIFY_PROMPT = re.compile(r"(?:Verify|Confirm(?:\s+password)?):\s*$", re.IGNORECASE)
_PASSWORD_PROMPT = re.compile(r"(?:\([^\r\n]+\)\s*)?Password:\s*$", re.IGNORECASE)
_HOST_CONFIRM = re.compile(r"Are you sure you want to continue connecting[^?]*\?\s*$", re.I)
_VNC_MODE_MARKERS = (
    "create a vnc connection password",
    "resetting vnc access password",
    "reseting vnc access password",
)


def parse_session_targets(output: str) -> list[SessionTarget]:
    result: list[SessionTarget] = []
    seen: set[tuple[str, int]] = set()
    for match in _TUNNEL.finditer(output):
        host = validate_workstation(match.group("host"))
        port = validate_port(int(match.group("remote")))
        key = (host, port)
        if key not in seen:
            seen.add(key)
            result.append(SessionTarget(host=host, remote_port=port))
    return result


def classify_auth_prompt(prompt: str) -> PromptKind | None:
    if _MFA_PROMPT.search(prompt):
        return PromptKind.MFA_CODE
    if _PASSWORD_PROMPT.search(prompt):
        return PromptKind.ECBE_PASSWORD
    return None


class RemotePromptScanner:
    """Recognize only expected trailing prompts from untrusted PTY output."""

    def __init__(self, *, vnc_password_command: bool = False) -> None:
        self._buffer = ""
        self._vnc_mode = vnc_password_command

    @property
    def buffer(self) -> str:
        return self._buffer

    def feed(self, text: str) -> PromptKind | str | None:
        self._buffer = (self._buffer + text)[-8192:]
        lowered = self._buffer.lower()
        if any(marker in lowered for marker in _VNC_MODE_MARKERS):
            self._vnc_mode = True
        if _MFA_PROMPT.search(self._buffer):
            self._buffer = ""
            return PromptKind.MFA_CODE
        if _HOST_CONFIRM.search(self._buffer):
            self._buffer = ""
            return "host-confirm"
        if _VERIFY_PROMPT.search(self._buffer):
            self._buffer = ""
            self._vnc_mode = False
            return PromptKind.VNC_PASSWORD_CONFIRM
        if _PASSWORD_PROMPT.search(self._buffer):
            self._buffer = ""
            if self._vnc_mode:
                return PromptKind.VNC_PASSWORD
            return PromptKind.ECBE_PASSWORD
        return None

