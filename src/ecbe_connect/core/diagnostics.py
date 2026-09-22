from __future__ import annotations

import asyncio
import socket

import keyring

from ecbe_connect.core.models import DiagnosticCheck
from ecbe_connect.core.validation import validate_gateway, validate_port
from ecbe_connect.viewers.launcher import SystemViewerLauncher


def _port_available(port: int) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


async def run_diagnostics(
    gateway: str,
    local_port: int,
    viewer_path: str | None,
) -> list[DiagnosticCheck]:
    checks: list[DiagnosticCheck] = []
    try:
        gateway = validate_gateway(gateway)
        checks.append(DiagnosticCheck("Gateway setting", True, "Gateway name is valid."))
    except Exception as exc:
        checks.append(DiagnosticCheck("Gateway setting", False, str(exc)))
        return checks

    try:
        await asyncio.get_running_loop().getaddrinfo(gateway, 22, type=socket.SOCK_STREAM)
        checks.append(DiagnosticCheck("Gateway DNS", True, "Gateway resolves successfully."))
    except OSError:
        checks.append(DiagnosticCheck("Gateway DNS", False, "Gateway name could not be resolved."))

    try:
        _reader, writer = await asyncio.wait_for(asyncio.open_connection(gateway, 22), timeout=5)
        writer.close()
        await writer.wait_closed()
        checks.append(DiagnosticCheck("SSH port", True, "TCP port 22 is reachable."))
    except (OSError, TimeoutError):
        checks.append(DiagnosticCheck("SSH port", False, "TCP port 22 is not reachable."))

    try:
        port = validate_port(local_port)
        available = _port_available(port)
        detail = (
            "Preferred port is available."
            if available
            else "Preferred port is already in use."
        )
        checks.append(
            DiagnosticCheck(
                "Local port",
                available,
                detail,
            )
        )
    except Exception as exc:
        checks.append(DiagnosticCheck("Local port", False, str(exc)))

    viewer = SystemViewerLauncher().detect(viewer_path)
    checks.append(
        DiagnosticCheck(
            "VNC viewer",
            viewer is not None,
            "A VNC viewer was found." if viewer else "Select or install RealVNC Viewer.",
        )
    )

    try:
        backend = keyring.get_keyring()
        priority = float(getattr(backend, "priority", 0))
        available = priority > 0
    except Exception:
        available = False
    checks.append(
        DiagnosticCheck(
            "Secure keychain",
            available,
            "Secure credential storage is available."
            if available
            else "No secure keychain is available; passwords will be prompted.",
        )
    )
    return checks
