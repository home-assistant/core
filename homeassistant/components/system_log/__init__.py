"""
Support for system log.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/system_log/
"""
from collections import deque
from io import StringIO
import logging
import re
import traceback

import voluptuous as vol

from homeassistant import __path__ as HOMEASSISTANT_PATH
from homeassistant.components.http import HomeAssistantView
import homeassistant.helpers.config_validation as cv
from homeassistant.const import EVENT_HOMEASSISTANT_STOP

CONF_MAX_ENTRIES = 'max_entries'
CONF_FIRE_EVENT = 'fire_event'
CONF_MESSAGE = 'message'
CONF_LEVEL = 'level'
CONF_LOGGER = 'logger'

DATA_SYSTEM_LOG = 'system_log'
DEFAULT_MAX_ENTRIES = 50
DEFAULT_FIRE_EVENT = False
DEPENDENCIES = ['http']
DOMAIN = 'system_log'

EVENT_SYSTEM_LOG = 'system_log_event'

SERVICE_CLEAR = 'clear'
SERVICE_WRITE = 'write'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_MAX_ENTRIES, default=DEFAULT_MAX_ENTRIES):
            cv.positive_int,
        vol.Optional(CONF_FIRE_EVENT, default=DEFAULT_FIRE_EVENT): cv.boolean,
    }),
}, extra=vol.ALLOW_EXTRA)

SERVICE_CLEAR_SCHEMA = vol.Schema({})
SERVICE_WRITE_SCHEMA = vol.Schema({
    vol.Required(CONF_MESSAGE): cv.string,
    vol.Optional(CONF_LEVEL, default='error'):
        vol.In(['debug', 'info', 'warning', 'error', 'critical']),
    vol.Optional(CONF_LOGGER): cv.string,
})


def _figure_out_source(record, call_stack, hass):
    paths = [HOMEASSISTANT_PATH[0], hass.config.config_dir]
    try:
        # If netdisco is installed check its path too.
        from netdisco import __path__ as netdisco_path
        paths.append(netdisco_path[0])
    except ImportError:
        pass
    # If a stack trace exists, extract file names from the entire call stack.
    # The other case is when a regular "log" is made (without an attached
    # exception). In that case, just use the file where the log was made from.
    if record.exc_info:
        stack = [x[0] for x in traceback.extract_tb(record.exc_info[2])]
    else:
        index = -1
        for i, frame in enumerate(call_stack):
            if frame == record.pathname:
                index = i
                break
        if index == -1:
            # For some reason we couldn't find pathname in the stack.
            stack = [record.pathname]
        else:
            stack = call_stack[0:index+1]

    # Iterate through the stack call (in reverse) and find the last call from
    # a file in Home Assistant. Try to figure out where error happened.
    paths_re = r'(?:{})/(.*)'.format('|'.join([re.escape(x) for x in paths]))
    for pathname in reversed(stack):

        # Try to match with a file within Home Assistant
        match = re.match(paths_re, pathname)
        if match:
            return match.group(1)
    # Ok, we don't know what this is
    return record.pathname


def _exception_as_string(exc_info):
    buf = StringIO()
    if exc_info:
        traceback.print_exception(*exc_info, file=buf)
    return buf.getvalue()


class LogErrorHandler(logging.Handler):
    """Log handler for error messages."""

    def __init__(self, hass, maxlen, fire_event):
        """Initialize a new LogErrorHandler."""
        super().__init__()
        self.hass = hass
        self.records = deque(maxlen=maxlen)
        self.fire_event = fire_event

    def _create_entry(self, record, call_stack):
        return {
            'timestamp': record.created,
            'level': record.levelname,
            'message': record.getMessage(),
            'exception': _exception_as_string(record.exc_info),
            'source': _figure_out_source(record, call_stack, self.hass),
            }

    def emit(self, record):
        """Save error and warning logs.

        Everything logged with error or warning is saved in local buffer. A
        default upper limit is set to 50 (older entries are discarded) but can
        be changed if needed.
        """
        if record.levelno >= logging.WARN:
            stack = []
            if not record.exc_info:
                stack = [f for f, _, _, _ in traceback.extract_stack()]

            entry = self._create_entry(record, stack)
            self.records.appendleft(entry)
            if self.fire_event:
                self.hass.bus.fire(EVENT_SYSTEM_LOG, entry)


async def async_setup(hass, config):
    """Set up the logger component."""
    conf = config.get(DOMAIN)
    if conf is None:
        conf = CONFIG_SCHEMA({DOMAIN: {}})[DOMAIN]

    handler = LogErrorHandler(hass, conf[CONF_MAX_ENTRIES],
                              conf[CONF_FIRE_EVENT])
    logging.getLogger().addHandler(handler)

    hass.http.register_view(AllErrorsView(handler))

    async def async_service_handler(service):
        """Handle logger services."""
        if service.service == 'clear':
            handler.records.clear()
            return
        if service.service == 'write':
            logger = logging.getLogger(
                service.data.get(CONF_LOGGER, '{}.external'.format(__name__)))
            level = service.data[CONF_LEVEL]
            getattr(logger, level)(service.data[CONF_MESSAGE])

    async def async_shutdown_handler(event):
        """Remove logging handler when Home Assistant is shutdown."""
        # This is needed as older logger instances will remain
        logging.getLogger().removeHandler(handler)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP,
                               async_shutdown_handler)

    hass.services.async_register(
        DOMAIN, SERVICE_CLEAR, async_service_handler,
        schema=SERVICE_CLEAR_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_WRITE, async_service_handler,
        schema=SERVICE_WRITE_SCHEMA)

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
        # deque is not serializable (it's just "list-like") so it must be
        # converted to a list before it can be serialized to json
        return self.json(list(self.handler.records))
