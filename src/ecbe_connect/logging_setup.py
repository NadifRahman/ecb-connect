from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from ecbe_connect.config import AppPaths
from ecbe_connect.security.redaction import RedactingFilter

_LOGGER_NAME = "ecbe_connect"


def configure_logging(paths: AppPaths | None = None) -> logging.Logger:
    app_paths = paths or AppPaths.system()
    app_paths.log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not logger.handlers:
        handler = RotatingFileHandler(
            app_paths.log_file,
            maxBytes=256_000,
            backupCount=2,
            encoding="utf-8",
        )
        handler.addFilter(RedactingFilter())
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
    return logger


def close_logging() -> None:
    logger = logging.getLogger(_LOGGER_NAME)
    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)
