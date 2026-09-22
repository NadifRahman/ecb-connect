from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

from platformdirs import user_cache_path, user_config_path, user_log_path

APP_NAME = "ECBE Connect"
APP_AUTHOR = "ECBE Connect contributors"
DEFAULT_GATEWAY = "pascal.ecb.torontomu.ca"


@dataclass(slots=True)
class AppConfig:
    username: str = ""
    gateway: str = DEFAULT_GATEWAY
    local_port: int = 5900
    viewer_path: str = ""
    remember_password: bool = False
    disclaimer_accepted: bool = False
    tray_notice_shown: bool = False
    release_url: str = ""


@dataclass(frozen=True, slots=True)
class AppPaths:
    config_dir: Path
    cache_dir: Path
    log_dir: Path

    @classmethod
    def system(cls) -> AppPaths:
        return cls(
            config_dir=user_config_path(APP_NAME, APP_AUTHOR),
            cache_dir=user_cache_path(APP_NAME, APP_AUTHOR),
            log_dir=user_log_path(APP_NAME, APP_AUTHOR),
        )

    @property
    def config_file(self) -> Path:
        return self.config_dir / "config.json"

    @property
    def known_hosts_file(self) -> Path:
        return self.config_dir / "known_hosts"

    @property
    def log_file(self) -> Path:
        return self.log_dir / "ecbe-connect.log"

    def disclaimer_marker(self, revision: int) -> Path:
        if revision < 1:
            raise ValueError("Disclaimer revision must be positive.")
        return self.config_dir / f"disclaimer-accepted-v{revision}"


class ConfigManager:
    def __init__(self, paths: AppPaths | None = None) -> None:
        self.paths = paths or AppPaths.system()

    def load(self) -> AppConfig:
        path = self.paths.config_file
        try:
            if not path.is_file():
                return AppConfig()
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return AppConfig()
        allowed = AppConfig.__dataclass_fields__.keys()
        values = {key: value for key, value in raw.items() if key in allowed}
        try:
            return AppConfig(**values)
        except TypeError:
            return AppConfig()

    def save(self, config: AppConfig) -> None:
        self.paths.config_dir.mkdir(parents=True, exist_ok=True)
        temp = self.paths.config_file.with_suffix(".tmp")
        temp.write_text(json.dumps(asdict(config), indent=2) + "\n", encoding="utf-8")
        self._restrict(temp)
        temp.replace(self.paths.config_file)
        self._restrict(self.paths.config_file)

    def disclaimer_is_accepted(self, revision: int) -> bool:
        try:
            return self.paths.disclaimer_marker(revision).is_file()
        except OSError:
            return False

    def record_disclaimer_acceptance(self, revision: int) -> None:
        self.paths.config_dir.mkdir(parents=True, exist_ok=True)
        marker = self.paths.disclaimer_marker(revision)
        temp = marker.with_name(f"{marker.name}.tmp")
        temp.write_text("accepted\n", encoding="utf-8")
        self._restrict(temp)
        temp.replace(marker)
        self._restrict(marker)

    def clear_files(self) -> None:
        paths = [self.paths.config_file, self.paths.known_hosts_file]
        if self.paths.config_dir.exists():
            paths.extend(self.paths.config_dir.glob("disclaimer-accepted-v*"))
        if self.paths.log_dir.exists():
            paths.extend(self.paths.log_dir.glob("ecbe-connect.log*"))
        for path in paths:
            try:
                path.unlink()
            except FileNotFoundError:
                pass

    @staticmethod
    def _restrict(path: Path) -> None:
        if os.name != "nt":
            path.chmod(0o600)
