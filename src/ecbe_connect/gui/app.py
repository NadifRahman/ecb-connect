from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QAction, QCloseEvent, QDesktopServices, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from ecbe_connect import __version__
from ecbe_connect.config import AppConfig, ConfigManager
from ecbe_connect.core.errors import UserCancelled
from ecbe_connect.core.models import AppEvent, ConnectionInfo, ConnectionProfile, ConnectionState
from ecbe_connect.gui.controller import CoreController, PromptRequest
from ecbe_connect.gui.help import HelpDialog
from ecbe_connect.legal import DISCLAIMER, DISCLAIMER_REVISION


def _asset(name: str) -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "assets" / name  # type: ignore[attr-defined]
    return Path(__file__).resolve().parents[3] / "assets" / name


class MainWindow(QMainWindow):
    def __init__(self, manager: ConfigManager, config: AppConfig, icon: QIcon) -> None:
        super().__init__()
        self.manager = manager
        self.config = config
        self.icon = icon
        self.controller = CoreController(manager)
        self.connected = False
        self.connection_info: ConnectionInfo | None = None
        self._quit_requested = False
        self._help: HelpDialog | None = None

        self.setWindowTitle("ECBE Connect - Unofficial")
        self.setWindowIcon(icon)
        self.resize(670, 560)
        self._build_ui()
        self._build_menu()
        self._build_tray()
        self._wire_controller()
        self._apply_config()

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        title = QLabel("ECBE Connect")
        title.setStyleSheet("font-size: 24px; font-weight: 600;")
        subtitle = QLabel(
            "Unofficial student utility. Credentials stay on this computer, "
            "and MFA is always manual."
        )
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        form = QFormLayout()
        self.username = QLineEdit()
        self.username.setPlaceholderText("ECBE username")
        self.gateway = QLineEdit()
        self.local_port = QSpinBox()
        self.local_port.setRange(1, 65535)
        self.viewer = QLineEdit()
        viewer_tip = (
            "Select the RealVNC Viewer executable, not its folder. Leave this blank to let "
            "ECBE Connect detect it automatically. Examples: rvncconnect.exe or vncviewer.exe "
            "on Windows, rvncconnect or vncviewer on macOS and Linux."
        )
        self.viewer.setPlaceholderText("Automatic detection, or select the RealVNC executable")
        self.viewer.setToolTip(viewer_tip)
        viewer_row = QHBoxLayout()
        viewer_row.addWidget(self.viewer)
        browse = QPushButton("Browse...")
        browse.setToolTip(viewer_tip)
        browse.clicked.connect(self._browse_viewer)
        viewer_row.addWidget(browse)
        self.remember = QCheckBox("Remember ECBE password in the operating-system keychain")
        form.addRow("Username", self.username)
        form.addRow("Gateway", self.gateway)
        form.addRow("Preferred local port", self.local_port)
        form.addRow("VNC viewer", viewer_row)
        form.addRow("", self.remember)
        layout.addLayout(form)

        primary = QHBoxLayout()
        self.connect_button = QPushButton("Connect and open VNC")
        self.connect_button.setDefault(True)
        self.disconnect_button = QPushButton("Disconnect")
        self.disconnect_button.setEnabled(False)
        primary.addWidget(self.connect_button)
        primary.addWidget(self.disconnect_button)
        layout.addLayout(primary)

        management = QHBoxLayout()
        sessions = QPushButton("Sessions")
        change_password = QPushButton("Change VNC password")
        kill = QPushButton("Kill session")
        doctor = QPushButton("Diagnostics")
        management.addWidget(sessions)
        management.addWidget(change_password)
        management.addWidget(kill)
        management.addWidget(doctor)
        layout.addLayout(management)

        self.status = QLabel("Ready")
        self.status.setStyleSheet("font-weight: 600;")
        self.address = QLabel("")
        self.address.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.events = QPlainTextEdit()
        self.events.setReadOnly(True)
        self.events.setMaximumBlockCount(200)
        layout.addWidget(self.status)
        layout.addWidget(self.address)
        layout.addWidget(self.events, 1)
        self.setCentralWidget(root)

        self.connect_button.clicked.connect(self._connect)
        self.disconnect_button.clicked.connect(self._disconnect)
        sessions.clicked.connect(lambda: self.controller.list_sessions(self._profile()))
        change_password.clicked.connect(
            lambda: self.controller.change_vnc_password(self._profile())
        )
        kill.clicked.connect(self._kill_session)
        doctor.clicked.connect(lambda: self.controller.diagnostics(self._profile()))

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        help_menu = self.menuBar().addMenu("Help")
        clear_action = QAction("Clear local data...", self)
        clear_action.triggered.connect(self._clear_data)
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self._quit)
        help_action = QAction("Open guides", self)
        help_action.triggered.connect(self._show_help)
        update_action = QAction("Check for updates", self)
        update_action.triggered.connect(self._check_updates)
        about_action = QAction("About and disclaimer", self)
        about_action.triggered.connect(self._about)
        file_menu.addAction(clear_action)
        file_menu.addSeparator()
        file_menu.addAction(quit_action)
        help_menu.addAction(help_action)
        help_menu.addAction(update_action)
        help_menu.addAction(about_action)

    def _build_tray(self) -> None:
        self.tray_available = QSystemTrayIcon.isSystemTrayAvailable()
        self.tray = QSystemTrayIcon(self.icon, self)
        menu = QMenu()
        show_action = menu.addAction("Show ECBE Connect")
        self.tray_status = menu.addAction("Status: disconnected")
        self.tray_status.setEnabled(False)
        copy_action = menu.addAction("Copy VNC address")
        reconnect_action = menu.addAction("Reconnect")
        disconnect_action = menu.addAction("Disconnect")
        menu.addSeparator()
        quit_action = menu.addAction("Quit")
        show_action.triggered.connect(self._show_window)
        copy_action.triggered.connect(self._copy_address)
        reconnect_action.triggered.connect(lambda: self.controller.reconnect(self._profile()))
        disconnect_action.triggered.connect(self._disconnect)
        quit_action.triggered.connect(self._quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_activated)
        if self.tray_available:
            self.tray.show()

    def _wire_controller(self) -> None:
        self.controller.prompt_requested.connect(self._handle_prompt)
        self.controller.event_received.connect(self._handle_event)
        self.controller.operation_failed.connect(self._operation_failed)
        self.controller.operation_result.connect(self._operation_result)
        self.controller.connected_changed.connect(self._connected_changed)

    def _apply_config(self) -> None:
        self.username.setText(self.config.username)
        self.gateway.setText(self.config.gateway)
        self.local_port.setValue(self.config.local_port)
        self.viewer.setText(self.config.viewer_path)
        self.remember.setChecked(self.config.remember_password)

    def _save_config(self) -> None:
        self.config.username = self.username.text().strip()
        self.config.gateway = self.gateway.text().strip()
        self.config.local_port = self.local_port.value()
        self.config.viewer_path = self.viewer.text().strip()
        self.config.remember_password = self.remember.isChecked()
        self.manager.save(self.config)

    def _profile(self) -> ConnectionProfile:
        return ConnectionProfile(
            username=self.username.text().strip(),
            gateway=self.gateway.text().strip(),
            local_port=self.local_port.value(),
            viewer_path=Path(self.viewer.text().strip()) if self.viewer.text().strip() else None,
            remember_password=self.remember.isChecked(),
        )

    def _connect(self) -> None:
        self._save_config()
        self.connect_button.setEnabled(False)
        self.status.setText("Connecting...")
        self.controller.start_connection(self._profile())

    def _disconnect(self) -> None:
        self.connect_button.setEnabled(False)
        self.disconnect_button.setEnabled(False)
        self.controller.stop_connection()

    def _browse_viewer(self) -> None:
        if sys.platform == "win32":
            start_directory = os.environ.get("ProgramFiles", "C:\\Program Files")
            file_filter = "Applications (*.exe);;All files (*)"
        elif sys.platform == "darwin":
            start_directory = "/Applications"
            file_filter = "All files (*)"
        else:
            start_directory = "/usr/bin"
            file_filter = "All files (*)"
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Select VNC viewer executable",
            start_directory,
            file_filter,
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if filename:
            self.viewer.setText(filename)

    def _kill_session(self) -> None:
        host, accepted = QInputDialog.getText(
            self, "Kill VNC session", "Workstation hostname (shown by Sessions):"
        )
        if not accepted or not host.strip():
            return
        answer = QMessageBox.question(
            self,
            "Confirm session stop",
            f"Stop the VNC session on {host.strip()}? Unsaved remote work may be lost.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.controller.kill_session(self._profile(), host.strip())

    def _handle_prompt(self, request: PromptRequest) -> None:
        if request.future.done():
            return
        try:
            if request.mode == "secret":
                value, accepted = QInputDialog.getText(
                    self,
                    "Authentication required",
                    request.message,
                    QLineEdit.EchoMode.Password,
                )
                if not accepted:
                    raise UserCancelled("Authentication was cancelled.")
                request.future.set_result(value)
            elif request.mode == "confirm":
                answer = QMessageBox.question(
                    self,
                    request.title,
                    request.message,
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                request.future.set_result(answer == QMessageBox.StandardButton.Yes)
            else:
                value, accepted = QInputDialog.getItem(
                    self, request.title, "Session", list(request.choices), 0, False
                )
                if not accepted:
                    raise UserCancelled("Session selection was cancelled.")
                request.future.set_result(value)
        except BaseException as exc:
            request.future.set_exception(exc)

    def _handle_event(self, event: AppEvent) -> None:
        self.status.setText(event.message)
        self.events.appendPlainText(event.message)
        if event.state == ConnectionState.DISCONNECTING:
            self.connect_button.setEnabled(False)
            self.disconnect_button.setEnabled(False)
        if event.state == ConnectionState.FAILED:
            self._connected_changed(False, None)
        if self.tray_available and event.level.value in {"warning", "error"}:
            icon = (
                QSystemTrayIcon.MessageIcon.Warning
                if event.level.value == "warning"
                else QSystemTrayIcon.MessageIcon.Critical
            )
            self.tray.showMessage("ECBE Connect", event.message, icon, 7000)

    def _operation_failed(self, name: str, message: str) -> None:
        self.connect_button.setEnabled(not self.connected)
        self.disconnect_button.setEnabled(self.connected)
        self.status.setText(message)
        QMessageBox.critical(self, f"{name} failed", message)

    def _operation_result(self, name: str, result: object) -> None:
        if name == "sessions":
            sessions = result if isinstance(result, list) else []
            text = (
                "\n".join(getattr(session, "label", str(session)) for session in sessions)
                if sessions
                else "No active sessions were reported."
            )
            QMessageBox.information(self, "Active VNC sessions", text)
        elif name == "doctor":
            checks = result if isinstance(result, list) else []
            lines = [
                f"{'OK' if check.ok else 'FAILED'} - {check.name}: {check.detail}"
                for check in checks
            ]
            QMessageBox.information(self, "Diagnostics", "\n".join(lines))
        elif name == "clear-data":
            self.config = AppConfig()
            self._apply_config()
            QMessageBox.information(
                self, "Local data removed", "ECBE Connect local data was removed."
            )

    def _connected_changed(self, connected: bool, result: object) -> None:
        self.connected = connected
        self.connect_button.setEnabled(not connected)
        self.disconnect_button.setEnabled(connected)
        self.connection_info = result if connected and isinstance(result, ConnectionInfo) else None
        address = self.connection_info.viewer_address if self.connection_info else ""
        self.address.setText(f"VNC address: {address}" if address else "")
        self.tray_status.setText("Status: connected" if connected else "Status: disconnected")
        self.tray.setToolTip("ECBE Connect - connected" if connected else "ECBE Connect")

    def _show_window(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in {
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        }:
            self._show_window()

    def _copy_address(self) -> None:
        if self.connection_info:
            QApplication.clipboard().setText(self.connection_info.viewer_address)
            self.tray.showMessage("ECBE Connect", "VNC address copied.")

    def _show_help(self) -> None:
        self._help = HelpDialog(self)
        self._help.show()

    def _about(self) -> None:
        QMessageBox.information(self, f"ECBE Connect {__version__}", DISCLAIMER)

    def _check_updates(self) -> None:
        if not self.config.release_url:
            QMessageBox.information(
                self,
                "Release page not configured",
                "The maintainer must set the canonical GitHub release URL before publishing.",
            )
            return
        QDesktopServices.openUrl(QUrl(self.config.release_url))

    def _clear_data(self) -> None:
        answer = QMessageBox.warning(
            self,
            "Clear local data",
            "Remove settings, logs, saved host keys, and the saved ECBE password?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.controller.clear_data(self.config.username)

    def _quit(self) -> None:
        if self.connected:
            answer = QMessageBox.question(
                self,
                "Disconnect and quit?",
                "Quitting will close the VNC tunnel.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self._quit_requested = True
        self.controller.shutdown()
        QApplication.quit()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._quit_requested:
            event.accept()
            return
        if self.connected:
            if self.tray_available:
                self.hide()
                if not self.config.tray_notice_shown:
                    self.tray.showMessage(
                        "ECBE Connect is still running",
                        "The SSH tunnel remains active. Use the tray icon to reopen or disconnect.",
                    )
                    self.config.tray_notice_shown = True
                    self.manager.save(self.config)
            else:
                self.showMinimized()
                QMessageBox.information(
                    self,
                    "Connection still active",
                    "This desktop has no system tray. The minimized window must remain open.",
                )
            event.ignore()
            return
        self._quit_requested = True
        self.controller.shutdown()
        QApplication.quit()
        event.accept()


def _accept_disclaimer(config: AppConfig, manager: ConfigManager) -> bool:
    if manager.disclaimer_is_accepted(DISCLAIMER_REVISION):
        return True
    if config.disclaimer_accepted:
        # Migrate releases which stored the acknowledgement only in config.json.
        try:
            manager.record_disclaimer_acceptance(DISCLAIMER_REVISION)
        except OSError:
            # The existing config acknowledgement is still sufficient for this run.
            pass
        return True
    box = QMessageBox()
    box.setWindowTitle("ECBE Connect - Unofficial software")
    box.setIcon(QMessageBox.Icon.Warning)
    box.setText(DISCLAIMER)
    box.setInformativeText("Select Accept to acknowledge this notice and continue.")
    box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
    box.setDefaultButton(QMessageBox.StandardButton.Cancel)
    if box.exec() != QMessageBox.StandardButton.Yes:
        return False
    config.disclaimer_accepted = True
    saved = False
    try:
        manager.save(config)
        saved = True
    except OSError:
        pass
    try:
        manager.record_disclaimer_acceptance(DISCLAIMER_REVISION)
        saved = True
    except OSError:
        pass
    if saved:
        return True
    QMessageBox.critical(
        None,
        "Unable to save acknowledgement",
        "ECBE Connect could not save the disclaimer acknowledgement. "
        "Check that your user configuration folder is writable and try again.",
    )
    return False


def run() -> None:
    application = QApplication(sys.argv)
    application.setApplicationName("ECBE Connect")
    application.setQuitOnLastWindowClosed(False)
    icon = QIcon(str(_asset("icon.svg")))
    application.setWindowIcon(icon)
    manager = ConfigManager()
    config = manager.load()
    if not _accept_disclaimer(config, manager):
        raise SystemExit(0)
    window = MainWindow(manager, config, icon)
    window.show()
    raise SystemExit(application.exec())


if __name__ == "__main__":
    run()
