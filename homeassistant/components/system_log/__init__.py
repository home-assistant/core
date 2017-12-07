"""
Support for system log.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/system_log/
"""
import os
import re
import asyncio
import logging
import traceback
from io import StringIO
from collections import deque

import voluptuous as vol

from homeassistant import __path__ as HOMEASSISTANT_PATH
from homeassistant.config import load_yaml_config_file
import homeassistant.helpers.config_validation as cv
from homeassistant.components.http import HomeAssistantView

DOMAIN = 'system_log'
DEPENDENCIES = ['http']
SERVICE_CLEAR = 'clear'

CONF_MAX_ENTRIES = 'max_entries'

DEFAULT_MAX_ENTRIES = 50

DATA_SYSTEM_LOG = 'system_log'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_MAX_ENTRIES,
                     default=DEFAULT_MAX_ENTRIES): cv.positive_int,
    }),
}, extra=vol.ALLOW_EXTRA)

SERVICE_CLEAR_SCHEMA = vol.Schema({})


class LogErrorHandler(logging.Handler):
    """Log handler for error messages."""

    def __init__(self, maxlen):
        """Initialize a new LogErrorHandler."""
        super().__init__()
        self.records = deque(maxlen=maxlen)

    def emit(self, record):
        """Save error and warning logs.

        Everyhing logged with error or warning is saved in local buffer. A
        default upper limit is set to 50 (older entries are discarded) but can
        be changed if neeeded.
        """
        if record.levelno >= logging.WARN:
            stack = []
            if not record.exc_info:
                try:
                    stack = [f for f, _, _, _ in traceback.extract_stack()]
                except ValueError:
                    # On Python 3.4 under py.test getting the stack might fail.
                    pass
            self.records.appendleft([record, stack])


@asyncio.coroutine
def async_setup(hass, config):
    """Set up the logger component."""
    conf = config.get(DOMAIN)

    if conf is None:
        conf = CONFIG_SCHEMA({DOMAIN: {}})[DOMAIN]

    handler = LogErrorHandler(conf.get(CONF_MAX_ENTRIES))
    logging.getLogger().addHandler(handler)

    hass.http.register_view(AllErrorsView(handler))

    @asyncio.coroutine
    def async_service_handler(service):
        """Handle logger services."""
        # Only one service so far
        handler.records.clear()

    descriptions = yield from hass.async_add_job(
        load_yaml_config_file, os.path.join(
            os.path.dirname(__file__), 'services.yaml'))

    hass.services.async_register(
        DOMAIN, SERVICE_CLEAR, async_service_handler,
        descriptions[DOMAIN].get(SERVICE_CLEAR),
        schema=SERVICE_CLEAR_SCHEMA)

    return True


def _figure_out_source(record, call_stack, hass):
    paths = [HOMEASSISTANT_PATH[0], hass.config.config_dir]
    try:
        # If netdisco is installed check its path too.
        from netdisco import __path__ as netdisco_path
        paths.append(netdisco_path[0])
    except ImportError:
        pass
    # If a stack trace exists, extract filenames from the entire call stack.
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
    # a file in HA. Try to figure out where error happened.
    for pathname in reversed(stack):

        # Try to match with a file within HA
        match = re.match(r'(?:{})/(.*)'.format('|'.join(paths)), pathname)
        if match:
            return match.group(1)
    # Ok, we don't know what this is
    return record.pathname


def _exception_as_string(exc_info):
    buf = StringIO()
    if exc_info:
        traceback.print_exception(*exc_info, file=buf)
    return buf.getvalue()


def _convert(record, call_stack, hass):
    return {
        'timestamp': record.created,
        'level': record.levelname,
        'message': record.getMessage(),
        'exception': _exception_as_string(record.exc_info),
        'source': _figure_out_source(record, call_stack, hass),
        }


class AllErrorsView(HomeAssistantView):
    """Get all logged errors and warnings."""

    url = "/api/error/all"
    name = "api:error:all"

    def __init__(self, handler):
        """Initialize a new AllErrorsView."""
        self.handler = handler

    @asyncio.coroutine
    def get(self, request):
        """Get all errors and warnings."""
        return self.json([_convert(x[0], x[1], request.app['hass'])
                          for x in self.handler.records])
