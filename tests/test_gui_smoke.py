from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QIcon

from ecbe_connect.config import AppConfig, AppPaths, ConfigManager
from ecbe_connect.gui.app import MainWindow, _accept_disclaimer
from ecbe_connect.gui.help import HelpDialog, docs_directory
from ecbe_connect.legal import DISCLAIMER_REVISION


def test_help_dialog_renders_repository_guides(qtbot) -> None:
    assert (docs_directory() / "using-the-app.md").is_file()
    dialog = HelpDialog()
    qtbot.addWidget(dialog)
    assert dialog.files.count() >= 7
    assert "ECBE" in dialog.browser.toPlainText()


def test_main_window_starts_with_shared_core(qtbot, tmp_path: Path) -> None:
    manager = ConfigManager(
        AppPaths(tmp_path / "config", tmp_path / "cache", tmp_path / "logs")
    )
    window = MainWindow(
        manager,
        AppConfig(username="student42", disclaimer_accepted=True),
        QIcon(),
    )
    qtbot.addWidget(window)
    assert window.username.text() == "student42"
    assert window.connect_button.isEnabled()
    assert "executable, not its folder" in window.viewer.toolTip()
    window.controller.shutdown()
    window._quit_requested = True


def test_legacy_disclaimer_acceptance_is_migrated_without_prompt(tmp_path: Path) -> None:
    manager = ConfigManager(
        AppPaths(tmp_path / "config", tmp_path / "cache", tmp_path / "logs")
    )

    assert _accept_disclaimer(AppConfig(disclaimer_accepted=True), manager)
    assert manager.disclaimer_is_accepted(DISCLAIMER_REVISION)
    assert _accept_disclaimer(AppConfig(), manager)
