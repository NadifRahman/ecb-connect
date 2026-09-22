from __future__ import annotations

import asyncio
from collections.abc import Coroutine, Sequence
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table
from rich.text import Text

from ecbe_connect.config import ConfigManager
from ecbe_connect.core.diagnostics import run_diagnostics
from ecbe_connect.core.errors import ECBEConnectError, UserCancelled
from ecbe_connect.core.models import AppEvent, ConnectionProfile, PromptKind
from ecbe_connect.core.service import ECBEConnectionService
from ecbe_connect.legal import DISCLAIMER
from ecbe_connect.runtime import build_service

app = typer.Typer(
    name="ecbe-connect",
    help="Unofficial ECBE SSH/VNC connection helper.",
    no_args_is_help=True,
)
console = Console()


class ConsolePrompts:
    async def request_secret(self, kind: PromptKind, message: str) -> str:
        del kind
        return await asyncio.to_thread(typer.prompt, message, hide_input=True)

    async def confirm(self, title: str, message: str) -> bool:
        console.print(f"\n[bold]{title}[/bold]\n{message}")
        return await asyncio.to_thread(typer.confirm, "Continue", default=False)

    async def choose(self, title: str, choices: Sequence[str]) -> str:
        console.print(f"\n[bold]{title}[/bold]")
        for index, choice in enumerate(choices, start=1):
            console.print(f"  {index}. {choice}")
        selected = int(await asyncio.to_thread(typer.prompt, "Selection", type=int))
        if not 1 <= selected <= len(choices):
            raise UserCancelled("Select a number shown in the session list.")
        return choices[selected - 1]


class ConsoleEvents:
    def emit(self, event: AppEvent) -> None:
        style = {"info": "cyan", "warning": "yellow", "error": "red"}[event.level.value]
        console.print(Text(event.message, style=style))


def _load_profile(manager: ConfigManager, *, local_port: int | None = None) -> ConnectionProfile:
    config = manager.load()
    if not config.username:
        config.username = typer.prompt("ECBE username")
        manager.save(config)
    return ConnectionProfile(
        username=config.username,
        gateway=config.gateway,
        local_port=local_port or config.local_port,
        viewer_path=Path(config.viewer_path) if config.viewer_path else None,
        remember_password=config.remember_password,
    )


def _service(manager: ConfigManager) -> ECBEConnectionService:
    return build_service(ConsolePrompts(), ConsoleEvents(), manager)


def _show_error(exc: BaseException) -> None:
    message = (
        str(exc) if isinstance(exc, ECBEConnectError) else "The operation failed unexpectedly."
    )
    console.print(f"[red]{message}[/red]")


@app.command()
def connect(
    no_viewer: Annotated[bool, typer.Option("--no-viewer", help="Do not launch RealVNC.")] = False,
    local_port: Annotated[
        int | None, typer.Option("--local-port", min=1, max=65535)
    ] = None,
) -> None:
    """Start or find a VNC session, open the tunnel, and launch the viewer."""

    async def operation() -> None:
        manager = ConfigManager()
        service = _service(manager)
        try:
            info = await service.connect(
                _load_profile(manager, local_port=local_port), launch_viewer=not no_viewer
            )
            console.print(f"[green]Tunnel active at {info.viewer_address}.[/green]")
            console.print("Leave this process running. Press Ctrl+C to disconnect.")
            await service.wait_until_disconnected()
        finally:
            await service.disconnect()

    try:
        asyncio.run(operation())
    except (KeyboardInterrupt, UserCancelled):
        console.print("Disconnected.")
    except BaseException as exc:
        _show_error(exc)
        raise typer.Exit(1) from None


@app.command("sessions")
def sessions_command() -> None:
    """List active ECBE VNC sessions."""

    async def operation() -> None:
        manager = ConfigManager()
        sessions = await _service(manager).list_sessions(_load_profile(manager))
        if not sessions:
            console.print("No active sessions were reported.")
            return
        table = Table("Workstation", "Remote VNC port")
        for session in sessions:
            table.add_row(session.host, str(session.remote_port))
        console.print(table)

    _run_short(operation())


@app.command("passwd")
def password_command() -> None:
    """Change the separate VNC access password."""

    async def operation() -> None:
        manager = ConfigManager()
        await _service(manager).change_vnc_password(_load_profile(manager))

    _run_short(operation())


@app.command("kill")
def kill_command(
    host: Annotated[str, typer.Argument(help="Workstation from `sessions`. ")],
) -> None:
    """Stop one selected VNC session after confirmation."""
    if not typer.confirm(f"Stop the VNC session on {host}?", default=False):
        raise typer.Abort()

    async def operation() -> None:
        manager = ConfigManager()
        await _service(manager).kill_session(_load_profile(manager), host)

    _run_short(operation())


@app.command("doctor")
def doctor_command() -> None:
    """Check local configuration, viewer, keychain, DNS, and SSH reachability."""
    manager = ConfigManager()
    config = manager.load()
    checks = asyncio.run(
        run_diagnostics(config.gateway, config.local_port, config.viewer_path or None)
    )
    table = Table("Check", "Result", "Detail")
    failed = False
    for check in checks:
        failed = failed or not check.ok
        table.add_row(check.name, "OK" if check.ok else "FAILED", check.detail)
    console.print(table)
    if failed:
        raise typer.Exit(1)


@app.command("config")
def config_command(
    username: Annotated[str | None, typer.Option(help="ECBE username.")] = None,
    gateway: Annotated[str | None, typer.Option(help="ECBE SSH gateway.")] = None,
    local_port: Annotated[int | None, typer.Option(min=1, max=65535)] = None,
    viewer: Annotated[Path | None, typer.Option(exists=True, dir_okay=False)] = None,
    remember_password: Annotated[
        bool | None, typer.Option("--remember-password/--no-remember-password")
    ] = None,
) -> None:
    """View or update non-secret settings."""
    manager = ConfigManager()
    config = manager.load()
    changed = False
    for name, value in (
        ("username", username),
        ("gateway", gateway),
        ("local_port", local_port),
        ("viewer_path", str(viewer) if viewer else None),
        ("remember_password", remember_password),
    ):
        if value is not None:
            setattr(config, name, value)
            changed = True
    if changed:
        manager.save(config)
        console.print("Settings saved. No password or MFA secret was written to the config file.")
    table = Table("Setting", "Value")
    table.add_row("Username", config.username or "not set")
    table.add_row("Gateway", config.gateway)
    table.add_row("Local port", str(config.local_port))
    table.add_row("Viewer", config.viewer_path or "automatic detection")
    table.add_row("Remember password", "yes (OS keychain)" if config.remember_password else "no")
    console.print(table)


@app.command("clear-data")
def clear_data_command() -> None:
    """Remove settings, logs, host keys, and the saved ECBE password."""
    console.print("This removes all local ECBE Connect data, including trusted host keys.")
    if not typer.confirm("Continue?", default=False):
        raise typer.Abort()

    async def operation() -> None:
        manager = ConfigManager()
        config = manager.load()
        await _service(manager).clear_local_data(manager, config.username)

    _run_short(operation())


@app.command("disclaimer")
def disclaimer_command() -> None:
    """Display the unofficial-use disclaimer."""
    console.print(DISCLAIMER)


def _run_short(coro: Coroutine[object, object, object]) -> None:
    try:
        asyncio.run(coro)
    except (KeyboardInterrupt, UserCancelled):
        console.print("Cancelled.")
    except BaseException as exc:
        _show_error(exc)
        raise typer.Exit(1) from None


def run() -> None:
    app()


if __name__ == "__main__":
    run()
