"""Support for system log."""
from collections import OrderedDict, deque
import logging
import re
import traceback

import voluptuous as vol

from homeassistant import __path__ as HOMEASSISTANT_PATH
from homeassistant.components.http import HomeAssistantView
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
import homeassistant.helpers.config_validation as cv

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


def _figure_out_source(record, call_stack, hass):
    paths = [HOMEASSISTANT_PATH[0], hass.config.config_dir]

    # If a stack trace exists, extract file names from the entire call stack.
    # The other case is when a regular "log" is made (without an attached
    # exception). In that case, just use the file where the log was made from.
    if record.exc_info:
        stack = [(x[0], x[1]) for x in traceback.extract_tb(record.exc_info[2])]
    else:
        index = -1
        for i, frame in enumerate(call_stack):
            if frame[0] == record.pathname:
                index = i
                break
        if index == -1:
            # For some reason we couldn't find pathname in the stack.
            stack = [(record.pathname, record.lineno)]
        else:
            stack = call_stack[0 : index + 1]

    # Iterate through the stack call (in reverse) and find the last call from
    # a file in Home Assistant. Try to figure out where error happened.
    paths_re = r"(?:{})/(.*)".format("|".join([re.escape(x) for x in paths]))
    for pathname in reversed(stack):

        # Try to match with a file within Home Assistant
        match = re.match(paths_re, pathname[0])
        if match:
            return [match.group(1), pathname[1]]
    # Ok, we don't know what this is
    return (record.pathname, record.lineno)


class LogEntry:
    """Store HA log entries."""

    def __init__(self, record, stack, source):
        """Initialize a log entry."""
        self.first_occurred = self.timestamp = record.created
        self.name = record.name
        self.level = record.levelname
        self.message = deque([record.getMessage()], maxlen=5)
        self.exception = ""
        self.root_cause = None
        if record.exc_info:
            self.exception = "".join(traceback.format_exception(*record.exc_info))
            _, _, tb = record.exc_info  # pylint: disable=invalid-name
            # Last line of traceback contains the root cause of the exception
            if traceback.extract_tb(tb):
                self.root_cause = str(traceback.extract_tb(tb)[-1])
        self.source = source
        self.count = 1
        self.hash = str([self.name, *self.source, self.root_cause])

    def to_dict(self):
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


class DedupStore(OrderedDict):
    """Data store to hold max amount of deduped entries."""

    def __init__(self, maxlen=50):
        """Initialize a new DedupStore."""
        super().__init__()
        self.maxlen = maxlen

    def add_entry(self, entry):
        """Add a new entry."""
        key = entry.hash

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

    def to_list(self):
        """Return reversed list of log entries - LIFO."""
        return [value.to_dict() for value in reversed(self.values())]


class LogErrorHandler(logging.Handler):
    """Log handler for error messages."""

    def __init__(self, hass, maxlen, fire_event):
        """Initialize a new LogErrorHandler."""
        super().__init__()
        self.hass = hass
        self.records = DedupStore(maxlen=maxlen)
        self.fire_event = fire_event

    def emit(self, record):
        """Save error and warning logs.

        Everything logged with error or warning is saved in local buffer. A
        default upper limit is set to 50 (older entries are discarded) but can
        be changed if needed.
        """
        if record.levelno >= logging.WARN:
            stack = []
            if not record.exc_info:
                stack = [(f[0], f[1]) for f in traceback.extract_stack()]

            entry = LogEntry(
                record, stack, _figure_out_source(record, stack, self.hass)
            )
            self.records.add_entry(entry)
            if self.fire_event:
                self.hass.bus.fire(EVENT_SYSTEM_LOG, entry.to_dict())


async def async_setup(hass, config):
    """Set up the logger component."""
    conf = config.get(DOMAIN)
    if conf is None:
        conf = CONFIG_SCHEMA({DOMAIN: {}})[DOMAIN]

    handler = LogErrorHandler(hass, conf[CONF_MAX_ENTRIES], conf[CONF_FIRE_EVENT])
    logging.getLogger().addHandler(handler)

    hass.http.register_view(AllErrorsView(handler))

    async def async_service_handler(service):
        """Handle logger services."""
        if service.service == "clear":
            handler.records.clear()
            return
        if service.service == "write":
            logger = logging.getLogger(
                service.data.get(CONF_LOGGER, f"{__name__}.external")
            )
            level = service.data[CONF_LEVEL]
            getattr(logger, level)(service.data[CONF_MESSAGE])

    async def async_shutdown_handler(event):
        """Remove logging handler when Home Assistant is shutdown."""
        # This is needed as older logger instances will remain
        logging.getLogger().removeHandler(handler)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_shutdown_handler)

    hass.services.async_register(
        DOMAIN, SERVICE_CLEAR, async_service_handler, schema=SERVICE_CLEAR_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_WRITE, async_service_handler, schema=SERVICE_WRITE_SCHEMA
    )

    return True


class AllErrorsView(HomeAssistantView):
    """Get all logged errors and warnings."""

    url = "/api/error/all"
    name = "api:error:all"

    def __init__(self, handler):
        """Initialize a new AllErrorsView."""
        self.handler = handler

    async def get(self, request):
        """Get all errors and warnings."""
        return self.json(self.handler.records.to_list())
