from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QDialog, QHBoxLayout, QListWidget, QTextBrowser, QWidget


def docs_directory() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "docs"  # type: ignore[attr-defined]
    return Path(__file__).resolve().parents[3] / "docs"


class HelpDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("ECBE Connect Help")
        self.resize(900, 650)
        layout = QHBoxLayout(self)
        self.files = QListWidget()
        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(True)
        layout.addWidget(self.files, 1)
        layout.addWidget(self.browser, 4)
        for path in sorted(docs_directory().glob("*.md")):
            self.files.addItem(path.name)
        self.files.currentTextChanged.connect(self._load)
        if self.files.count():
            self.files.setCurrentRow(0)

    def _load(self, filename: str) -> None:
        path = docs_directory() / filename
        try:
            markdown = path.read_text(encoding="utf-8")
        except OSError:
            markdown = "# Help unavailable\n\nThe bundled guide could not be opened."
        self.browser.document().setBaseUrl(path.parent.as_uri() + "/")
        self.browser.setMarkdown(markdown)
        self.browser.moveCursor(QTextCursor.MoveOperation.Start)
