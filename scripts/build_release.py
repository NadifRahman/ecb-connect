from __future__ import annotations

import hashlib
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
BUILD = ROOT / "build"
RELEASE = ROOT / "release"


def run(*arguments: str) -> None:
    subprocess.run(arguments, cwd=ROOT, check=True)  # noqa: S603


def pyinstaller(*arguments: str) -> None:
    run(sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", *arguments)


def add_data(source: str, destination: str) -> str:
    return f"{source}{os.pathsep}{destination}"


def build_icons() -> Path | None:
    renderer = QSvgRenderer(str(ROOT / "assets" / "icon.svg"))
    image = QImage(256, 256, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    image.save(str(ROOT / "assets" / "icon.png"), "PNG")
    if platform.system() != "Windows":
        return None
    icon_path = ROOT / "assets" / "icon.ico"
    if not image.save(str(icon_path), "ICO"):
        return None
    return icon_path


def build() -> Path:
    for path in (DIST, BUILD, RELEASE):
        if path.exists():
            shutil.rmtree(path)
    RELEASE.mkdir()
    icon_path = build_icons()

    common: tuple[str, ...] = (
        "--paths",
        "src",
        "--collect-submodules",
        "keyring.backends",
        "--collect-data",
        "keyring",
        "--exclude-module",
        "pytest",
        "--exclude-module",
        "mypy",
        "--exclude-module",
        "bandit",
        "--exclude-module",
        "pip_audit",
        "--add-data",
        add_data("docs", "docs"),
        "--add-data",
        add_data("assets", "assets"),
    )
    gui_options = common
    if icon_path is not None:
        gui_options += ("--icon", str(icon_path))
    pyinstaller(
        *gui_options,
        "--name",
        "ECBE Connect",
        "--windowed",
        "src/ecbe_connect/gui/app.py",
    )
    pyinstaller(
        *common,
        "--name",
        "ecbe-connect-cli",
        "--onefile",
        "src/ecbe_connect/cli/app.py",
    )

    system = platform.system().lower()
    machine = platform.machine().lower().replace("amd64", "x86_64")
    stem = f"ecbe-connect-0.1.1-{system}-{machine}"
    gui_output = DIST / ("ECBE Connect.app" if system == "darwin" else "ECBE Connect")
    cli_name = "ecbe-connect-cli.exe" if system == "windows" else "ecbe-connect-cli"
    cli_output = DIST / cli_name

    staging = BUILD / stem
    staging.mkdir(parents=True)
    if gui_output.is_dir():
        shutil.copytree(gui_output, staging / gui_output.name)
    else:
        shutil.copy2(gui_output, staging / gui_output.name)
    shutil.copy2(cli_output, staging / cli_name)
    for filename in ("README.md", "LICENSE", "SECURITY.md", "THIRD_PARTY_NOTICES.md"):
        shutil.copy2(ROOT / filename, staging / filename)
    shutil.copytree(ROOT / "docs", staging / "docs")

    if system == "windows":
        archive = RELEASE / f"{stem}.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as output:
            for path in sorted(staging.rglob("*")):
                if path.is_file():
                    output.write(path, path.relative_to(staging.parent))
    else:
        archive = RELEASE / f"{stem}.tar.gz"
        with tarfile.open(archive, "w:gz") as output:
            output.add(staging, arcname=staging.name)
    return archive


def write_checksums() -> None:
    lines = []
    for path in sorted(RELEASE.iterdir()):
        if path.name == "SHA256SUMS.txt" or not path.is_file():
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.name}")
    (RELEASE / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="ascii")


if __name__ == "__main__":
    if "--checksums-only" in sys.argv:
        write_checksums()
    else:
        built = build()
        write_checksums()
        print(f"Built {built.relative_to(ROOT)}")
