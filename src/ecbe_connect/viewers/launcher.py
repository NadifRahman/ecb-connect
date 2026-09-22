from __future__ import annotations

import os
import shutil

# Launching the installed viewer is the intended feature; arguments never use a shell.
import subprocess  # nosec B404
import sys
from pathlib import Path

from ecbe_connect.core.errors import ViewerNotFound


def _candidate_paths() -> list[Path]:
    if sys.platform == "win32":
        roots = [
            os.environ.get("ProgramFiles", ""),
            os.environ.get("ProgramFiles(x86)", ""),
            os.environ.get("LOCALAPPDATA", ""),
        ]
        suffixes = [
            Path("RealVNC/VNC Viewer/vncviewer.exe"),
            Path("RealVNC/VNC Viewer/VNC Viewer.exe"),
            Path("RealVNC/RealVNC Connect/rvncconnect.exe"),
            Path("RealVNC Connect/RealVNC Connect.exe"),
        ]
        return [Path(root) / suffix for root in roots if root for suffix in suffixes]
    if sys.platform == "darwin":
        return [
            Path("/Applications/VNC Viewer.app/Contents/MacOS/vncviewer"),
            Path("/Applications/RealVNC Viewer.app/Contents/MacOS/vncviewer"),
            Path("/Applications/RealVNC Connect.app/Contents/MacOS/rvncconnect"),
            Path("/Applications/RealVNC Connect.app/Contents/MacOS/RealVNC Connect"),
        ]
    return [
        Path("/usr/bin/vncviewer"),
        Path("/usr/local/bin/vncviewer"),
        Path("/usr/bin/rvncconnect"),
        Path("/usr/local/bin/rvncconnect"),
    ]


class SystemViewerLauncher:
    def detect(self, configured_path: str | None = None) -> str | None:
        if configured_path:
            configured = Path(configured_path).expanduser()
            if configured.is_file():
                return str(configured)
        for executable in ("vncviewer", "rvncconnect"):
            located = shutil.which(executable)
            if located:
                return located
        for candidate in _candidate_paths():
            if candidate.is_file():
                return str(candidate)
        return None

    def launch(self, address: str, configured_path: str | None = None) -> None:
        executable = self.detect(configured_path)
        if not executable:
            raise ViewerNotFound(
                "RealVNC Viewer was not found. Install it or select its executable in Settings."
            )
        arguments = [executable]
        if _is_realvnc(executable):
            # Associate command-line direct connections with RealVNC's address book so its own
            # optional password store and connection settings can be reused. No password is passed.
            arguments.append("-useaddressbook")
        arguments.append(address)
        # The address is validated and supplied as a discrete argument. No shell is involved.
        subprocess.Popen(  # nosec B603  # noqa: S603
            arguments,
            shell=False,
            close_fds=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def _is_realvnc(executable: str) -> bool:
    name = Path(executable).name.lower()
    return name in {"vncviewer", "vncviewer.exe", "rvncconnect", "rvncconnect.exe"}
