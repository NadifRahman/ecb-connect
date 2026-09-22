from __future__ import annotations

import logging
import re

_PATTERNS = (
    re.compile(r"(?i)(password\s*[=:]\s*)\S+"),
    re.compile(r"(?i)(verification\s+code\s*[=:]\s*)\d{6}"),
    re.compile(r"\b\d{6}\b"),
    re.compile(r"(?i)(home[/\\](?:student\d+)[/\\])[^\s/\\]+"),
)


def redact(value: str) -> str:
    result = value
    for pattern in _PATTERNS:
        result = pattern.sub(
            lambda match: f"{match.group(1) if match.lastindex else ''}[REDACTED]",
            result,
        )
    return result


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(record.getMessage())
        record.args = ()
        return True
