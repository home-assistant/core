"""
Component that will help set the level of logging for components.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/logger/
"""
import asyncio
import logging
import os
from collections import OrderedDict

import voluptuous as vol

from homeassistant.config import load_yaml_config_file
import homeassistant.helpers.config_validation as cv

DOMAIN = 'logger'

DATA_LOGGER = 'logger'

SERVICE_SET_LEVEL = 'set_level'

LOGSEVERITY = {
    'CRITICAL': 50,
    'FATAL': 50,
    'ERROR': 40,
    'WARNING': 30,
    'WARN': 30,
    'INFO': 20,
    'DEBUG': 10,
    'NOTSET': 0
}

LOGGER_DEFAULT = 'default'
LOGGER_LOGS = 'logs'

_VALID_LOG_LEVEL = vol.All(vol.Upper, vol.In(LOGSEVERITY))

SERVICE_SET_LEVEL_SCHEMA = vol.Schema({cv.string: _VALID_LOG_LEVEL})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(LOGGER_DEFAULT): _VALID_LOG_LEVEL,
        vol.Optional(LOGGER_LOGS): vol.Schema({cv.string: _VALID_LOG_LEVEL}),
    }),
}, extra=vol.ALLOW_EXTRA)


def set_level(hass, logs):
    """Set log level for components."""
    hass.services.call(DOMAIN, SERVICE_SET_LEVEL, logs)


class HomeAssistantLogFilter(logging.Filter):
    """A log filter."""

    # pylint: disable=no-init
    def __init__(self, logfilter):
        """Initialize the filter."""
        super().__init__()

        self.logfilter = logfilter

    def filter(self, record):
        """Filter the log entries."""
        # Log with filtered severity
        if LOGGER_LOGS in self.logfilter:
            for filtername in self.logfilter[LOGGER_LOGS]:
                logseverity = self.logfilter[LOGGER_LOGS][filtername]
                if record.name.startswith(filtername):
                    return record.levelno >= logseverity

        # Log with default severity
        default = self.logfilter[LOGGER_DEFAULT]
        return record.levelno >= default


@asyncio.coroutine
def async_setup(hass, config):
    """Set up the logger component."""
    logfilter = {}

    # Set default log severity
    logfilter[LOGGER_DEFAULT] = LOGSEVERITY['DEBUG']
    if LOGGER_DEFAULT in config.get(DOMAIN):
        logfilter[LOGGER_DEFAULT] = LOGSEVERITY[
            config.get(DOMAIN)[LOGGER_DEFAULT]
        ]

    def set_log_levels(logpoints):
        """Set the specified log levels."""
        logs = {}

        # Preserve existing logs
        if LOGGER_LOGS in logfilter:
            logs.update(logfilter[LOGGER_LOGS])

        # Add new logpoints mapped to correc severity
        for key, value in logpoints.items():
            logs[key] = LOGSEVERITY[value]

        logfilter[LOGGER_LOGS] = OrderedDict(
            sorted(
                logs.items(),
                key=lambda t: len(t[0]),
                reverse=True
            )
        )

    logger = logging.getLogger('')
    logger.setLevel(logging.NOTSET)

    # Set log filter for all log handler
    for handler in logging.root.handlers:
        handler.setLevel(logging.NOTSET)
        handler.addFilter(HomeAssistantLogFilter(logfilter))

    if LOGGER_LOGS in config.get(DOMAIN):
        set_log_levels(config.get(DOMAIN)[LOGGER_LOGS])

    @asyncio.coroutine
    def async_service_handler(service):
        """Handle logger services."""
        set_log_levels(service.data)

    descriptions = yield from hass.async_add_job(
        load_yaml_config_file, os.path.join(
            os.path.dirname(__file__), 'services.yaml'))

    hass.services.async_register(
        DOMAIN, SERVICE_SET_LEVEL, async_service_handler,
        descriptions[DOMAIN].get(SERVICE_SET_LEVEL),
        schema=SERVICE_SET_LEVEL_SCHEMA)

    return True
