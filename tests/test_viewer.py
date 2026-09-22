from __future__ import annotations

import subprocess
from pathlib import Path

from ecbe_connect.viewers.launcher import SystemViewerLauncher, _is_realvnc


def test_realvnc_executable_names_across_platforms() -> None:
    assert _is_realvnc("C:/Program Files/RealVNC/RealVNC Connect/rvncconnect.exe")
    assert _is_realvnc("/Applications/RealVNC Connect.app/Contents/MacOS/rvncconnect")
    assert _is_realvnc("/usr/bin/vncviewer")
    assert not _is_realvnc("/usr/bin/other-viewer")


def test_viewer_uses_argument_list_and_never_passes_credentials(
    tmp_path: Path, monkeypatch
) -> None:
    executable = tmp_path / "vncviewer.exe"
    executable.write_bytes(b"")
    captured: dict[str, object] = {}

    def fake_popen(args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return object()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    SystemViewerLauncher().launch("127.0.0.1::5900", str(executable))
    assert captured["args"] == [
        str(executable),
        "-useaddressbook",
        "127.0.0.1::5900",
    ]
    assert captured["kwargs"]["shell"] is False  # type: ignore[index]
    assert "password" not in " ".join(captured["args"])  # type: ignore[arg-type]


def test_non_realvnc_viewer_does_not_receive_realvnc_options(
    tmp_path: Path, monkeypatch
) -> None:
    executable = tmp_path / "other-viewer.exe"
    executable.write_bytes(b"")
    captured: list[str] = []

    def fake_popen(args, **kwargs):
        del kwargs
        captured.extend(args)
        return object()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    SystemViewerLauncher().launch("127.0.0.1::5900", str(executable))
    assert captured == [str(executable), "127.0.0.1::5900"]
