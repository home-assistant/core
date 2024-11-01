"""Support for system log."""

from __future__ import annotations

from collections import OrderedDict, deque
import logging
import re
import sys
import traceback
from types import FrameType
from typing import Any, cast

import voluptuous as vol

from homeassistant import __path__ as HOMEASSISTANT_PATH
from homeassistant.components import websocket_api
from homeassistant.const import EVENT_HOMEASSISTANT_CLOSE
from homeassistant.core import Event, HomeAssistant, ServiceCall, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

type KeyType = tuple[str, tuple[str, int], tuple[str, int, str] | None]

CONF_MAX_ENTRIES = "max_entries"
CONF_FIRE_EVENT = "fire_event"
CONF_MESSAGE = "message"
CONF_LEVEL = "level"
CONF_LOGGER = "logger"

DATA_SYSTEM_LOG = "system_log"
DEFAULT_MAX_ENTRIES = 50
DEFAULT_FIRE_EVENT = False
DOMAIN = "system_log"

EVENT_SYSTEM_LOG = "system_log_event"

SERVICE_CLEAR = "clear"
SERVICE_WRITE = "write"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(
                    CONF_MAX_ENTRIES, default=DEFAULT_MAX_ENTRIES
                ): cv.positive_int,
                vol.Optional(CONF_FIRE_EVENT, default=DEFAULT_FIRE_EVENT): cv.boolean,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_CLEAR_SCHEMA = vol.Schema({})
SERVICE_WRITE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_MESSAGE): cv.string,
        vol.Optional(CONF_LEVEL, default="error"): vol.In(
            ["debug", "info", "warning", "error", "critical"]
        ),
        vol.Optional(CONF_LOGGER): cv.string,
    }
)


def _figure_out_source(
    record: logging.LogRecord,
    paths_re: re.Pattern[str],
    extracted_tb: list[tuple[FrameType, int]] | None = None,
) -> tuple[str, int]:
    """Figure out where a log message came from."""
    # If a stack trace exists, extract file names from the entire call stack.
    # The other case is when a regular "log" is made (without an attached
    # exception). In that case, just use the file where the log was made from.
    if record.exc_info:
        source: list[tuple[FrameType, int]] = extracted_tb or list(
            traceback.walk_tb(record.exc_info[2])
        )
        stack = [
            (tb_frame.f_code.co_filename, tb_line_no) for tb_frame, tb_line_no in source
        ]
        for i, (filename, _) in enumerate(stack):
            # Slice the stack to the first frame that matches
            # the record pathname.
            if filename == record.pathname:
                stack = stack[0 : i + 1]
                break
        # Iterate through the stack call (in reverse) and find the last call from
        # a file in Home Assistant. Try to figure out where error happened.
        for path, line_number in reversed(stack):
            # Try to match with a file within Home Assistant
            if match := paths_re.match(path):
                return (cast(str, match.group(1)), line_number)
    else:
        #
        # We need to figure out where the log call came from if we
        # don't have an exception.
        #
        # We do this by walking up the stack until we find the first
        # frame match the record pathname so the code below
        # can be used to reverse the remaining stack frames
        # and find the first one that is from a file within Home Assistant.
        #
        # We do not call traceback.extract_stack() because it is
        # it makes many stat() syscalls calls which do blocking I/O,
        # and since this code is running in the event loop, we need to avoid
        # blocking I/O.

        frame = sys._getframe(4)  # noqa: SLF001
        #
        # We use _getframe with 4 to skip the following frames:
        #
        # Jump 2 frames up to get to the actual caller
        # since we are in a function, and always called from another function
        # that are never the original source of the log message.
        #
        # Next try to skip any frames that are from the logging module
        # We know that the logger module typically has 5 frames itself
        # but it may change in the future so we are conservative and
        # only skip 2.
        #
        # _getframe is cpython only but we are already using cpython specific
        # code everywhere in HA so it's fine as its unlikely we will ever
        # support other python implementations.
        #
        # Iterate through the stack call (in reverse) and find the last call from
        # a file in Home Assistant. Try to figure out where error happened.
        while back := frame.f_back:
            if match := paths_re.match(frame.f_code.co_filename):
                return (cast(str, match.group(1)), frame.f_lineno)
            frame = back

    # Ok, we don't know what this is
    return (record.pathname, record.lineno)


def _safe_get_message(record: logging.LogRecord) -> str:
    """Get message from record and handle exceptions.

    This code will be unreachable during a pytest run
    because pytest installs a logging handler that
    will prevent this code from being reached.

    Calling record.getMessage() can raise an exception
    if the log message does not contain sufficient arguments.

    As there is no guarantees about which exceptions
    that can be raised, we catch all exceptions and
    return a generic message.

    This must be manually tested when changing the code.
    """
    try:
        return record.getMessage()
    except Exception as ex:  # noqa: BLE001
        try:
            return f"Bad logger message: {record.msg} ({record.args})"
        except Exception:  # noqa: BLE001
            return f"Bad logger message: {ex}"


class LogEntry:
    """Store HA log entries."""

    __slots__ = (
        "first_occurred",
        "timestamp",
        "name",
        "level",
        "message",
        "exception",
        "root_cause",
        "source",
        "count",
        "key",
    )

    def __init__(
        self,
        record: logging.LogRecord,
        paths_re: re.Pattern,
        formatter: logging.Formatter | None = None,
        figure_out_source: bool = False,
    ) -> None:
        """Initialize a log entry."""
        self.first_occurred = self.timestamp = record.created
        self.name = record.name
        self.level = record.levelname
        # See the docstring of _safe_get_message for why we need to do this.
        # This must be manually tested when changing the code.
        self.message = deque([_safe_get_message(record)], maxlen=5)
        self.exception = ""
        self.root_cause: tuple[str, int, str] | None = None
        extracted_tb: list[tuple[FrameType, int]] | None = None
        if record.exc_info:
            if formatter and record.exc_text is None:
                record.exc_text = formatter.formatException(record.exc_info)
            self.exception = record.exc_text or ""
            if extracted := list(traceback.walk_tb(record.exc_info[2])):
                # Last line of traceback contains the root cause of the exception
                extracted_tb = extracted
                tb_frame, tb_line_no = extracted[-1]
                self.root_cause = (
                    tb_frame.f_code.co_filename,
                    tb_line_no,
                    tb_frame.f_code.co_name,
                )
        if figure_out_source:
            self.source = _figure_out_source(record, paths_re, extracted_tb)
        else:
            self.source = (record.pathname, record.lineno)
        self.count = 1
        self.key = (self.name, self.source, self.root_cause)

    def to_dict(self) -> dict[str, Any]:
        """Convert object into dict to maintain backward compatibility."""
        return {
            "name": self.name,
            "message": list(self.message),
            "level": self.level,
            "source": self.source,
            "timestamp": self.timestamp,
            "exception": self.exception,
            "count": self.count,
            "first_occurred": self.first_occurred,
        }


class DedupStore(OrderedDict[KeyType, LogEntry]):
    """Data store to hold max amount of deduped entries."""

    def __init__(self, maxlen: int = 50) -> None:
        """Initialize a new DedupStore."""
        super().__init__()
        self.maxlen = maxlen

    def add_entry(self, entry: LogEntry) -> None:
        """Add a new entry."""
        key = entry.key

        if key in self:
            # Update stored entry
            existing = self[key]
            existing.count += 1
            existing.timestamp = entry.timestamp

            if entry.message[0] not in existing.message:
                existing.message.append(entry.message[0])

            self.move_to_end(key)
        else:
            self[key] = entry

        if len(self) > self.maxlen:
            # Removes the first record which should also be the oldest
            self.popitem(last=False)

    def to_list(self) -> list[dict[str, Any]]:
        """Return reversed list of log entries - LIFO."""
        return [value.to_dict() for value in reversed(self.values())]


class LogErrorHandler(logging.Handler):
    """Log handler for error messages."""

    def __init__(
        self,
        hass: HomeAssistant,
        maxlen: int,
        fire_event: bool,
        paths_re: re.Pattern[str],
    ) -> None:
        """Initialize a new LogErrorHandler."""
        super().__init__()
        self.hass = hass
        self.records = DedupStore(maxlen=maxlen)
        self.fire_event = fire_event
        self.paths_re = paths_re

    def emit(self, record: logging.LogRecord) -> None:
        """Save error and warning logs.

        Everything logged with error or warning is saved in local buffer. A
        default upper limit is set to 50 (older entries are discarded) but can
        be changed if needed.
        """
        entry = LogEntry(
            record, self.paths_re, formatter=self.formatter, figure_out_source=True
        )
        self.records.add_entry(entry)
        if self.fire_event:
            self.hass.bus.fire(EVENT_SYSTEM_LOG, entry.to_dict())


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the logger component."""
    if (conf := config.get(DOMAIN)) is None:
        conf = CONFIG_SCHEMA({DOMAIN: {}})[DOMAIN]

    hass_path: str = HOMEASSISTANT_PATH[0]
    config_dir = hass.config.config_dir
    paths_re = re.compile(rf"(?:{re.escape(hass_path)}|{re.escape(config_dir)})/(.*)")
    handler = LogErrorHandler(
        hass, conf[CONF_MAX_ENTRIES], conf[CONF_FIRE_EVENT], paths_re
    )
    handler.setLevel(logging.WARNING)

    hass.data[DOMAIN] = handler

    @callback
    def _async_stop_handler(_: Event) -> None:
        """Cleanup handler."""
        logging.root.removeHandler(handler)
        del hass.data[DOMAIN]

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_CLOSE, _async_stop_handler)

    logging.root.addHandler(handler)

    websocket_api.async_register_command(hass, list_errors)

    @callback
    def _async_clear_service_handler(service: ServiceCall) -> None:
        handler.records.clear()

    @callback
    def _async_write_service_handler(service: ServiceCall) -> None:
        name = service.data.get(CONF_LOGGER, f"{__name__}.external")
        logger = logging.getLogger(name)
        level = service.data[CONF_LEVEL]
        getattr(logger, level)(service.data[CONF_MESSAGE])

    hass.services.async_register(
        DOMAIN, SERVICE_CLEAR, _async_clear_service_handler, schema=SERVICE_CLEAR_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_WRITE, _async_write_service_handler, schema=SERVICE_WRITE_SCHEMA
    )

    return True


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "system_log/list"})
@callback
def list_errors(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """List all possible diagnostic handlers."""
    connection.send_result(
        msg["id"],
        hass.data[DOMAIN].records.to_list(),
    )
