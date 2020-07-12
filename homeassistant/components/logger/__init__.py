"""Support for setting the level of logging for components."""
import logging
import re

import voluptuous as vol

import homeassistant.helpers.config_validation as cv

DOMAIN = "logger"

DATA_LOGGER = "logger"

SERVICE_SET_DEFAULT_LEVEL = "set_default_level"
SERVICE_SET_LEVEL = "set_level"

HIGHEST_LOG_LEVEL = logging.CRITICAL

LOGSEVERITY = {
    "CRITICAL": 50,
    "FATAL": 50,
    "ERROR": 40,
    "WARNING": 30,
    "WARN": 30,
    "INFO": 20,
    "DEBUG": 10,
    "NOTSET": 0,
}

LOGGER_DEFAULT = "default"
LOGGER_LOGS = "logs"

ATTR_LEVEL = "level"

_VALID_LOG_LEVEL = vol.All(vol.Upper, vol.In(LOGSEVERITY))

SERVICE_SET_DEFAULT_LEVEL_SCHEMA = vol.Schema({ATTR_LEVEL: _VALID_LOG_LEVEL})
SERVICE_SET_LEVEL_SCHEMA = vol.Schema({cv.string: _VALID_LOG_LEVEL})

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(LOGGER_DEFAULT): _VALID_LOG_LEVEL,
                vol.Optional(LOGGER_LOGS): vol.Schema({cv.string: _VALID_LOG_LEVEL}),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


class HomeAssistantLogFilter(logging.Filter):
    """A log filter."""

    def __init__(self):
        """Initialize the filter."""
        super().__init__()

        self._default = None
        self._logs = {}
        self._log_rx = None

    def update_default_level(self, default_level):
        """Update the default logger level."""
        self._default = default_level

    def update_log_filter(self, logs):
        """Rebuild the internal filter from new config."""
        #
        # A precompiled regex is used to avoid
        # the overhead of a list transversal
        #
        # Sort to make sure the longer
        # names are always matched first
        # so they take precedence of the shorter names
        # to allow for more granular settings.
        #
        names_by_len = sorted(list(logs), key=len, reverse=True)
        self._log_rx = re.compile("".join(["^(?:", "|".join(names_by_len), ")"]))
        self._logs = logs

    def set_logger_level(self):
        """Find the lowest log level set to allow logger to pre-filter log messages."""
        #
        # We set the root logger level to lowest log level
        # specified in default or for in the log filter so
        # logger.isEnabledFor function will work as designed
        # to avoid making logger records that will always be
        # discarded.
        #
        # This can make the logger performance significantly
        # faster if no integrations are requesting debug logs
        # because we can avoid the record creation and filtering
        # overhead.
        #
        logger = logging.getLogger("")
        logger.setLevel(min(HIGHEST_LOG_LEVEL, self._default, *self._logs.values()))

    def filter(self, record):
        """Filter the log entries."""
        # Log with filtered severity
        if self._log_rx:
            match = self._log_rx.match(record.name)
            if match:
                return record.levelno >= self._logs[match.group(0)]

        # Log with default severity
        return record.levelno >= self._default


async def async_setup(hass, config):
    """Set up the logger component."""
    logfilter = {}
    hass_filter = HomeAssistantLogFilter()

    def set_default_log_level(level):
        """Set the default log level for components."""
        logfilter[LOGGER_DEFAULT] = LOGSEVERITY[level]
        hass_filter.update_default_level(LOGSEVERITY[level])

    def set_log_levels(logpoints):
        """Set the specified log levels."""
        logs = {}

        # Preserve existing logs
        if LOGGER_LOGS in logfilter:
            logs.update(logfilter[LOGGER_LOGS])

        # Add new logpoints mapped to correct severity
        for key, value in logpoints.items():
            logs[key] = LOGSEVERITY[value]

        logfilter[LOGGER_LOGS] = logs

        hass_filter.update_log_filter(logs)

    # Set default log severity
    if LOGGER_DEFAULT in config.get(DOMAIN):
        set_default_log_level(config.get(DOMAIN)[LOGGER_DEFAULT])
    else:
        set_default_log_level("DEBUG")

    # Set log filter for all log handler
    for handler in logging.root.handlers:
        handler.setLevel(logging.NOTSET)
        handler.addFilter(hass_filter)

    if LOGGER_LOGS in config.get(DOMAIN):
        set_log_levels(config.get(DOMAIN)[LOGGER_LOGS])

    hass_filter.set_logger_level()

    async def async_service_handler(service):
        """Handle logger services."""
        if service.service == SERVICE_SET_DEFAULT_LEVEL:
            set_default_log_level(service.data.get(ATTR_LEVEL))
        else:
            set_log_levels(service.data)
        hass_filter.set_logger_level()

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_DEFAULT_LEVEL,
        async_service_handler,
        schema=SERVICE_SET_DEFAULT_LEVEL_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_LEVEL,
        async_service_handler,
        schema=SERVICE_SET_LEVEL_SCHEMA,
    )

    return True
