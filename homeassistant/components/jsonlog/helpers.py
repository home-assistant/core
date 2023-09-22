"""Helpers for the logger integration."""
from __future__ import annotations

from datetime import UTC, datetime
import logging
import os
from queue import SimpleQueue

from pythonjsonlogger import jsonlogger

from homeassistant.util.logging import HomeAssistantQueueHandler

from .const import LOGGER, LogAttribute


class JsonFormatter(jsonlogger.JsonFormatter):
    """Formats log messages as JSON objects."""

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        """Format log record created timestamp as ISO8601 string."""
        created = datetime.fromtimestamp(record.created, tz=UTC)
        return created.isoformat(sep="T", timespec="milliseconds")


def setup_listener_handler(
    *,
    logpath: str,
    log_backup_count: int = 2,
    log_max_bytes: int = 5 * 1024**2,
) -> logging.handlers.RotatingFileHandler | None:
    """Set up a file-based log handler to attach to the queue listener."""

    path_exists = os.path.isfile(logpath)
    log_dir = os.path.dirname(logpath)

    # Check if we can write to the error log if it exists or that
    # we can create files in the containing directory if not.
    if (path_exists and not os.access(logpath, os.W_OK)) or (
        not path_exists and not os.access(log_dir, os.W_OK)
    ):
        LOGGER.error("Unable to set up log file %s (access denied)", logpath)

    handler = logging.handlers.RotatingFileHandler(
        logpath,
        backupCount=log_backup_count,
        maxBytes=log_max_bytes,
    )

    handler.setFormatter(logging.Formatter("%(message)s"))
    return handler


def setup_queue_handler(
    *, queue: SimpleQueue[logging.Handler], logattrs: list[LogAttribute]
) -> HomeAssistantQueueHandler:
    """Set up a queue log handler with JSON formatter."""

    formatter = JsonFormatter(" ".join([f"%({attr})" for attr in logattrs]))  # type: ignore[no-untyped-call]
    handler = HomeAssistantQueueHandler(queue)
    handler.setFormatter(formatter)
    return handler
