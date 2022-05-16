"""Support for setting the level of logging for components."""
import logging

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from . import websocket_api
from .const import (
    ATTR_LEVEL,
    DEFAULT_LOGSEVERITY,
    DOMAIN,
    LOGGER_DEFAULT,
    LOGGER_FILTERS,
    LOGGER_LOGS,
    LOGSEVERITY,
    SERVICE_SET_DEFAULT_LEVEL,
    SERVICE_SET_LEVEL,
)
from .helpers import set_default_log_level, set_log_levels

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

    websocket_api.async_load_websocket_api(hass)

    # Set default log severity
    if DOMAIN in config:
        set_default_log_level(
            hass, config[DOMAIN].get(LOGGER_DEFAULT, DEFAULT_LOGSEVERITY)
        )

        if LOGGER_LOGS in config[DOMAIN]:
            set_log_levels(hass, config[DOMAIN][LOGGER_LOGS])

        if LOGGER_FILTERS in config[DOMAIN]:
            for key, value in config[DOMAIN][LOGGER_FILTERS].items():
                logger = logging.getLogger(key)
                _add_log_filter(logger, value)

    @callback
    def async_service_handler(service: ServiceCall) -> None:
        """Handle logger services."""
        if service.service == SERVICE_SET_DEFAULT_LEVEL:
            set_default_log_level(hass, service.data.get(ATTR_LEVEL))
        else:
            set_log_levels(hass, service.data)

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
