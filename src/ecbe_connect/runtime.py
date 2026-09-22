from __future__ import annotations

import logging

from ecbe_connect.config import ConfigManager
from ecbe_connect.core.models import AppEvent
from ecbe_connect.core.protocols import EventSink, PromptProvider
from ecbe_connect.core.service import ECBEConnectionService
from ecbe_connect.core.ssh_backend import GatewayConnector
from ecbe_connect.logging_setup import configure_logging
from ecbe_connect.security.credentials import KeyringCredentialStore
from ecbe_connect.security.hostkeys import HostKeyManager
from ecbe_connect.viewers.launcher import SystemViewerLauncher


class CompositeEventSink:
    def __init__(self, visible: EventSink, logger: logging.Logger) -> None:
        self.visible = visible
        self.logger = logger

    def emit(self, event: AppEvent) -> None:
        self.visible.emit(event)
        # Persist event categories only. Usernames, paths, prompts, and server output stay out.
        self.logger.log(
            {
                "info": logging.INFO,
                "warning": logging.WARNING,
                "error": logging.ERROR,
            }[event.level.value],
            "event=%s state=%s",
            event.code,
            event.state.value,
        )


def build_service(
    prompts: PromptProvider,
    events: EventSink,
    config: ConfigManager,
) -> ECBEConnectionService:
    safe_events = CompositeEventSink(events, configure_logging(config.paths))
    return ECBEConnectionService(
        connector=GatewayConnector(HostKeyManager(config.paths.known_hosts_file)),
        prompts=prompts,
        credentials=KeyringCredentialStore(),
        viewer=SystemViewerLauncher(),
        events=safe_events,
    )
