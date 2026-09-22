from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from ecbe_connect.config import AppConfig, AppPaths, ConfigManager
from ecbe_connect.legal import DISCLAIMER_REVISION
from ecbe_connect.security.redaction import RedactingFilter, redact


def paths(root: Path) -> AppPaths:
    return AppPaths(root / "config", root / "cache", root / "logs")


def test_config_contains_preferences_but_no_credentials(tmp_path: Path) -> None:
    manager = ConfigManager(paths(tmp_path))
    manager.save(AppConfig(username="student", remember_password=True))
    raw = manager.paths.config_file.read_text(encoding="utf-8")
    data = json.loads(raw)
    assert data["username"] == "student"
    assert "password" not in raw.lower().replace("remember_password", "")
    if os.name != "nt":
        assert manager.paths.config_file.stat().st_mode & 0o777 == 0o600


def test_disclaimer_acceptance_is_stored_separately_and_versioned(tmp_path: Path) -> None:
    manager = ConfigManager(paths(tmp_path))
    assert not manager.disclaimer_is_accepted(DISCLAIMER_REVISION)

    manager.record_disclaimer_acceptance(DISCLAIMER_REVISION)

    assert manager.disclaimer_is_accepted(DISCLAIMER_REVISION)
    assert not manager.disclaimer_is_accepted(DISCLAIMER_REVISION + 1)


def test_clear_removes_config_hostkeys_and_rotated_logs(tmp_path: Path) -> None:
    manager = ConfigManager(paths(tmp_path))
    for path in (
        manager.paths.config_file,
        manager.paths.known_hosts_file,
        manager.paths.log_file,
        manager.paths.log_dir / "ecbe-connect.log.1",
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("data", encoding="utf-8")
    manager.record_disclaimer_acceptance(DISCLAIMER_REVISION)
    manager.clear_files()
    assert not manager.paths.config_file.exists()
    assert not manager.paths.known_hosts_file.exists()
    assert not manager.disclaimer_is_accepted(DISCLAIMER_REVISION)
    assert not list(manager.paths.log_dir.glob("ecbe-connect.log*"))


def test_redaction_removes_common_secret_shapes() -> None:
    value = "password=canary-secret Verification code: 123456 home/student1/sampleuser"
    cleaned = redact(value)
    assert "canary-secret" not in cleaned
    assert "123456" not in cleaned
    assert "sampleuser" not in cleaned


def test_logging_filter_formats_then_redacts_arguments() -> None:
    record = logging.LogRecord(
        "test",
        logging.INFO,
        __file__,
        1,
        "password=%s event=%s",
        ("canary-secret", "connected"),
        None,
    )
    assert RedactingFilter().filter(record)
    assert record.msg == "password=[REDACTED] event=connected"
    assert record.args == ()
