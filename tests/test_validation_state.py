from __future__ import annotations

import pytest

from ecbe_connect.core.errors import ValidationError
from ecbe_connect.core.models import ConnectionProfile, ConnectionState
from ecbe_connect.core.state import ConnectionStateMachine, InvalidStateTransition
from ecbe_connect.core.validation import validate_gateway, validate_profile, validate_workstation


def test_validates_and_normalizes_profile() -> None:
    profile = validate_profile(
        ConnectionProfile(" student42 ", "PASCAL.ECB.TORONTOMU.CA.", 5900)
    )
    assert profile.username == "student42"
    assert profile.gateway == "pascal.ecb.torontomu.ca"


@pytest.mark.parametrize(
    "value",
    ["example.com", "pascal.ecb.torontomu.ca;whoami", "", "user@host"],
)
def test_rejects_invalid_gateways(value: str) -> None:
    with pytest.raises(ValidationError):
        validate_gateway(value)


def test_workstation_allowlist() -> None:
    assert validate_workstation("CMP92.EE.RYERSON.CA.") == "cmp92.ee.ryerson.ca"
    with pytest.raises(ValidationError):
        validate_workstation("cmp92.example.net")


def test_state_machine_happy_path_and_invalid_jump() -> None:
    machine = ConnectionStateMachine()
    with pytest.raises(InvalidStateTransition):
        machine.transition(ConnectionState.CONNECTED)
    for state in (
        ConnectionState.AUTHENTICATING,
        ConnectionState.PREPARING_SESSION,
        ConnectionState.OPENING_TUNNEL,
        ConnectionState.LAUNCHING_VIEWER,
        ConnectionState.CONNECTED,
        ConnectionState.DISCONNECTING,
        ConnectionState.IDLE,
    ):
        machine.transition(state)
    assert machine.state == ConnectionState.IDLE
