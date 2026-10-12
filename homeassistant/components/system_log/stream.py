"""Stream the raw Home Assistant log to websocket subscribers."""

from collections import deque
from collections.abc import Callable
import logging
import os
import re
from typing import Any, override

import probatio

from homeassistant.components import websocket_api
from homeassistant.const import KEY_DATA_LOGGING
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.debounce import Debouncer
from homeassistant.loader import IntegrationNotFound, async_get_integration
from homeassistant.util.hass_dict import HassKey
from homeassistant.util.logging import HomeAssistantQueueHandler

from .const import (
    RAW_BACKLOG_LINES,
    RAW_BUFFER_LINES,
    RAW_INTEGRATION_BACKLOG_LINES,
    RAW_UPDATE_COOLDOWN,
)

_LOGGER = logging.getLogger(__name__)

DATA_RAW_LOG_STREAM: HassKey[RawLogStreamHandler] = HassKey("system_log_raw")

# Logs every message it sends, including the streamed lines
WEBSOCKET_CONNECTION_LOGGER = "homeassistant.components.websocket_api.http.connection"

# Start of a record in the log file, the logger name is the first group
LOG_FILE_RECORD = re.compile(r"\d{4}-\d{2}-\d{2} \S+ [A-Z]+ \(.*?\) \[([^\]]+)\] ")

TAIL_BLOCK_SIZE = 64 * 1024

ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")

FALLBACK_FORMAT = (
    "%(asctime)s.%(msecs)03d %(levelname)s (%(threadName)s) [%(name)s] %(message)s"
)


def _console_formatter() -> logging.Formatter:
    """Return the formatter of the console log, which may add colors."""
    for handler in logging.root.handlers:
        if isinstance(handler, HomeAssistantQueueHandler) and handler.listener:
            for listener_handler in handler.listener.handlers:
                if (
                    type(listener_handler) is logging.StreamHandler
                    and listener_handler.formatter
                ):
                    return listener_handler.formatter
    return logging.Formatter(FALLBACK_FORMAT)


def _read_log_tail(path: str, lines: int) -> list[str]:
    """Return the last lines of the log file."""
    data = b""
    try:
        with open(path, "rb") as log_file:
            start = log_file.seek(0, os.SEEK_END)
            # Read blocks from the end until there are enough lines
            while start and data.count(b"\n") <= lines:
                block = min(start, TAIL_BLOCK_SIZE)
                start = log_file.seek(start - block)
                data = log_file.read(block) + data
    except OSError:
        return []
    tail = data.decode(errors="replace").splitlines()
    if start:
        # The first line is most likely cut off
        tail = tail[1:]
    return tail[-lines:]


def _matches_loggers(name: str, loggers: tuple[str, ...]) -> bool:
    """Return if the logger name is one of the loggers or a child of them."""
    return any(name == logger or name.startswith(f"{logger}.") for logger in loggers)


def _read_log_records(path: str, loggers: tuple[str, ...], lines: int) -> list[str]:
    """Return the last lines of the log file logged by the loggers."""
    backlog: deque[str] = deque(maxlen=lines)
    matches = False
    try:
        with open(path, encoding="utf-8", errors="replace") as log_file:
            for line in log_file:
                if record := LOG_FILE_RECORD.match(line):
                    matches = _matches_loggers(record.group(1), loggers)
                # Lines without a record start belong to the previous record
                if matches:
                    backlog.append(line.rstrip("\n"))
    except OSError:
        return []
    return list(backlog)


class RawLogStreamHandler(logging.Handler):
    """Collect formatted log lines while there are subscribers."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the handler."""
        super().__init__()
        self.hass = hass
        self._lines: deque[tuple[str, str]] = deque(maxlen=RAW_BUFFER_LINES)
        self._subscribers: dict[
            Callable[[list[str]], None], tuple[str, ...] | None
        ] = {}
        # Replaced, never changed, as emit reads it from other threads
        self._wanted_loggers: tuple[str, ...] | None = ()
        self._update_debouncer = Debouncer(
            hass,
            _LOGGER,
            cooldown=RAW_UPDATE_COOLDOWN,
            immediate=True,
            function=self._async_send_lines,
        )

    @override
    def emit(self, record: logging.LogRecord) -> None:
        """Buffer the formatted record."""
        if (
            record.levelno == logging.DEBUG
            and record.name == WEBSOCKET_CONNECTION_LOGGER
        ):
            return
        wanted_loggers = self._wanted_loggers
        if wanted_loggers is not None and not _matches_loggers(
            record.name, wanted_loggers
        ):
            return
        try:
            self._lines.append((record.name, self.format(record)))
        except Exception:  # noqa: BLE001
            self.handleError(record)
            return
        # emit runs in the thread that logged the record
        self.hass.loop.call_soon_threadsafe(self._update_debouncer.async_schedule_call)

    @callback
    def _async_send_lines(self) -> None:
        """Send the buffered lines to all subscribers."""
        records = [self._lines.popleft() for _ in range(len(self._lines))]
        if not records:
            return
        for subscriber, loggers in self._subscribers.items():
            lines = [
                line
                for name, line in records
                if loggers is None or _matches_loggers(name, loggers)
            ]
            if lines:
                subscriber(lines)

    @callback
    def async_flush(self) -> None:
        """Send the buffered lines now."""
        self._async_send_lines()

    @callback
    def async_subscribe(
        self,
        subscriber: Callable[[list[str]], None],
        loggers: tuple[str, ...] | None = None,
    ) -> CALLBACK_TYPE:
        """Subscribe to new log lines, optionally only from the given loggers."""
        if not self._subscribers:
            self.setFormatter(_console_formatter())
            logging.root.addHandler(self)
        self._subscribers[subscriber] = loggers
        self._async_update_wanted_loggers()

        @callback
        def _async_unsubscribe() -> None:
            self._subscribers.pop(subscriber, None)
            self._async_update_wanted_loggers()
            if not self._subscribers:
                logging.root.removeHandler(self)
                self._lines.clear()

        return _async_unsubscribe

    @callback
    def _async_update_wanted_loggers(self) -> None:
        """Update the loggers any subscriber wants, None for all loggers."""
        if None in self._subscribers.values():
            self._wanted_loggers = None
            return
        self._wanted_loggers = tuple(
            {
                logger
                for loggers in self._subscribers.values()
                if loggers is not None
                for logger in loggers
            }
        )

    @callback
    def async_shutdown(self) -> None:
        """Stop streaming."""
        logging.root.removeHandler(self)
        self._update_debouncer.async_shutdown()


@callback
def async_setup_raw_log_stream(hass: HomeAssistant) -> RawLogStreamHandler:
    """Set up the raw log stream."""
    handler = hass.data[DATA_RAW_LOG_STREAM] = RawLogStreamHandler(hass)
    websocket_api.async_register_command(hass, subscribe_raw_log)
    return handler


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        probatio.Required("type"): "system_log/subscribe_raw",
        probatio.Optional("integration"): str,
    }
)
@websocket_api.async_response
async def subscribe_raw_log(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Subscribe to the raw log, starting with the end of the log file.

    With an integration, only its lines are streamed, starting with its lines
    from the log file.
    """
    msg_id = msg["id"]
    loggers: tuple[str, ...] | None = None
    if domain := msg.get("integration"):
        try:
            integration = await async_get_integration(hass, domain)
        except IntegrationNotFound:
            connection.send_error(
                msg_id, websocket_api.ERR_NOT_FOUND, "Integration not found"
            )
            return
        # Includes the loggers of the libraries it uses
        loggers = (integration.pkg_path, *(integration.loggers or ()))

    # Collect new lines while reading the log file, so none get lost in between
    pending: list[str] = []
    collecting = True

    @callback
    def _async_send_lines(lines: list[str]) -> None:
        if collecting:
            pending.extend(lines)
            return
        connection.send_message(websocket_api.event_message(msg_id, lines))

    connection.subscriptions[msg_id] = hass.data[DATA_RAW_LOG_STREAM].async_subscribe(
        _async_send_lines, loggers
    )

    backlog: list[str] = []
    if path := hass.data.get(KEY_DATA_LOGGING):
        if loggers:
            backlog = await hass.async_add_executor_job(
                _read_log_records, path, loggers, RAW_INTEGRATION_BACKLOG_LINES
            )
        else:
            backlog = await hass.async_add_executor_job(
                _read_log_tail, path, RAW_BACKLOG_LINES
            )

    hass.data[DATA_RAW_LOG_STREAM].async_flush()
    # The log file may already contain some of the collected lines
    in_backlog = set(backlog)
    new_lines = [
        line
        for line in pending
        if ANSI_ESCAPE.sub("", line).split("\n", 1)[0] not in in_backlog
    ]
    collecting = False
    connection.send_result(msg_id)
    _async_send_lines(backlog + new_lines)
