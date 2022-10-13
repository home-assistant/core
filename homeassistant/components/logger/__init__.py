"""Support for setting the level of logging for components."""
import logging

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

DOMAIN = "logger"

SERVICE_SET_DEFAULT_LEVEL = "set_default_level"
SERVICE_SET_LEVEL = "set_level"

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
LOGGER_FILTERS = "filters"

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
                vol.Optional(LOGGER_FILTERS): vol.Schema({cv.string: [cv.is_regex]}),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the logger component."""
    hass.data[DOMAIN] = {}
    logging.setLoggerClass(_get_logger_class(hass.data[DOMAIN]))

    @callback
    def set_default_log_level(level):
        """Set the default log level for components."""
        _set_log_level(logging.getLogger(""), level)

    @callback
    def set_log_levels(logpoints):
        """Set the specified log levels."""
        hass.data[DOMAIN].update(logpoints)
        for key, value in logpoints.items():
            _set_log_level(logging.getLogger(key), value)

    # Set default log severity
    logger_config = config.get(DOMAIN, {})

    if LOGGER_DEFAULT in logger_config:
        set_default_log_level(logger_config[LOGGER_DEFAULT])

    if LOGGER_LOGS in logger_config:
        set_log_levels(config[DOMAIN][LOGGER_LOGS])

    if LOGGER_FILTERS in logger_config:
        for key, value in logger_config[LOGGER_FILTERS].items():
            logger = logging.getLogger(key)
            _add_log_filter(logger, value)

    @callback
    def async_service_handler(service: ServiceCall) -> None:
        """Handle logger services."""
        if service.service == SERVICE_SET_DEFAULT_LEVEL:
            set_default_log_level(service.data.get(ATTR_LEVEL))
        else:
            set_log_levels(service.data)

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


def _set_log_level(logger, level):
    """Set the log level.

    Any logger fetched before this integration is loaded will use old class.
    """
    getattr(logger, "orig_setLevel", logger.setLevel)(LOGSEVERITY[level])


def _add_log_filter(logger, patterns):
    """Add a Filter to the logger based on a regexp of the filter_str."""

    def filter_func(logrecord):
        return not any(p.search(logrecord.getMessage()) for p in patterns)

    logger.addFilter(filter_func)


def _get_logger_class(hass_overrides):
    """Create a logger subclass.

    logging.setLoggerClass checks if it is a subclass of Logger and
    so we cannot use partial to inject hass_overrides.
    """

    class HassLogger(logging.Logger):
        """Home Assistant aware logger class."""

        def setLevel(self, level) -> None:
            """Set the log level unless overridden."""
            if self.name in hass_overrides:
                return

            super().setLevel(level)

        # pylint: disable=invalid-name
        def orig_setLevel(self, level) -> None:
            """Set the log level."""
            super().setLevel(level)

    return HassLogger
