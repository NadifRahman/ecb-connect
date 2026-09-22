from __future__ import annotations

import re

from ecbe_connect.core.errors import ValidationError
from ecbe_connect.core.models import ConnectionProfile

_USERNAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_HOST = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?$")
_WORKSTATION = re.compile(
    r"^[a-zA-Z0-9-]+(?:\.(?:ee\.ryerson\.ca|ecb\.torontomu\.ca))?$"
)
_ALLOWED_GATEWAY_SUFFIXES = (".ecb.torontomu.ca", ".ee.ryerson.ca")


def validate_username(username: str) -> str:
    value = username.strip()
    if not _USERNAME.fullmatch(value) or "@" in value:
        raise ValidationError("Enter an ECBE username without spaces or '@'.")
    return value


def validate_gateway(host: str) -> str:
    value = host.strip().lower().rstrip(".")
    if not _HOST.fullmatch(value) or not value.endswith(_ALLOWED_GATEWAY_SUFFIXES):
        raise ValidationError("Gateway must be an ECBE torontomu.ca or legacy ryerson.ca host.")
    return value


def validate_workstation(host: str) -> str:
    value = host.strip().lower().rstrip(".")
    if not _WORKSTATION.fullmatch(value):
        raise ValidationError("The server returned an invalid workstation hostname.")
    return value


def validate_port(port: int) -> int:
    if not 1 <= port <= 65535:
        raise ValidationError("Port must be between 1 and 65535.")
    return port


def validate_profile(profile: ConnectionProfile) -> ConnectionProfile:
    return ConnectionProfile(
        username=validate_username(profile.username),
        gateway=validate_gateway(profile.gateway),
        local_port=validate_port(profile.local_port),
        viewer_path=profile.viewer_path,
        remember_password=profile.remember_password,
    )

