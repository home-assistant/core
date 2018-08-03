"""
Component that will help set the level of logging for components.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/logger/
"""
import logging
from collections import OrderedDict

import voluptuous as vol

import homeassistant.helpers.config_validation as cv

DOMAIN = 'logger'

DATA_LOGGER = 'logger'

SERVICE_SET_DEFAULT_LEVEL = 'set_default_level'
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

ATTR_LEVEL = 'level'

_VALID_LOG_LEVEL = vol.All(vol.Upper, vol.In(LOGSEVERITY))

SERVICE_SET_DEFAULT_LEVEL_SCHEMA = vol.Schema({ATTR_LEVEL: _VALID_LOG_LEVEL})
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


async def async_setup(hass, config):
    """Set up the logger component."""
    logfilter = {}

    def set_default_log_level(level):
        """Set the default log level for components."""
        logfilter[LOGGER_DEFAULT] = LOGSEVERITY[level]

    def set_log_levels(logpoints):
        """Set the specified log levels."""
        logs = {}

        # Preserve existing logs
        if LOGGER_LOGS in logfilter:
            logs.update(logfilter[LOGGER_LOGS])

        # Add new logpoints mapped to correct severity
        for key, value in logpoints.items():
            logs[key] = LOGSEVERITY[value]

        logfilter[LOGGER_LOGS] = OrderedDict(
            sorted(
                logs.items(),
                key=lambda t: len(t[0]),
                reverse=True
            )
        )

    # Set default log severity
    if LOGGER_DEFAULT in config.get(DOMAIN):
        set_default_log_level(config.get(DOMAIN)[LOGGER_DEFAULT])
    else:
        set_default_log_level('DEBUG')

    logger = logging.getLogger('')
    logger.setLevel(logging.NOTSET)

    # Set log filter for all log handler
    for handler in logging.root.handlers:
        handler.setLevel(logging.NOTSET)
        handler.addFilter(HomeAssistantLogFilter(logfilter))

    if LOGGER_LOGS in config.get(DOMAIN):
        set_log_levels(config.get(DOMAIN)[LOGGER_LOGS])

    async def async_service_handler(service):
        """Handle logger services."""
        if service.service == SERVICE_SET_DEFAULT_LEVEL:
            set_default_log_level(service.data.get(ATTR_LEVEL))
        else:
            set_log_levels(service.data)

    hass.services.async_register(
        DOMAIN, SERVICE_SET_DEFAULT_LEVEL, async_service_handler,
        schema=SERVICE_SET_DEFAULT_LEVEL_SCHEMA)

    hass.services.async_register(
        DOMAIN, SERVICE_SET_LEVEL, async_service_handler,
        schema=SERVICE_SET_LEVEL_SCHEMA)

    return True
