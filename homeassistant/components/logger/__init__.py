"""Support for setting the level of logging for components."""
from __future__ import annotations

import logging
import re

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from . import websocket_api
from .const import (
    ATTR_LEVEL,
    DOMAIN,
    EVENT_LOGGING_CHANGED,  # noqa: F401
    LOGGER_DEFAULT,
    LOGGER_FILTERS,
    LOGGER_LOGS,
    LOGSEVERITY,
    SERVICE_SET_DEFAULT_LEVEL,
    SERVICE_SET_LEVEL,
)
from .helpers import (
    LoggerDomainConfig,
    LoggerSettings,
    set_default_log_level,
    set_log_levels,
)

_VALID_LOG_LEVEL = vol.All(vol.Upper, vol.In(LOGSEVERITY), LOGSEVERITY.__getitem__)

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

    settings = LoggerSettings(hass, config)

    domain_config = hass.data[DOMAIN] = LoggerDomainConfig({}, settings)
    logging.setLoggerClass(_get_logger_class(domain_config.overrides))

    websocket_api.async_load_websocket_api(hass)

    await settings.async_load()

    # Set default log severity and filter
    logger_config = config.get(DOMAIN, {})

    if LOGGER_DEFAULT in logger_config:
        set_default_log_level(hass, logger_config[LOGGER_DEFAULT])

    if LOGGER_FILTERS in logger_config:
        log_filters: dict[str, list[re.Pattern]] = logger_config[LOGGER_FILTERS]
        for key, value in log_filters.items():
            _add_log_filter(logging.getLogger(key), value)

    # Combine log levels configured in configuration.yaml with log levels set by frontend
    combined_logs = await settings.async_get_levels(hass)
    set_log_levels(hass, combined_logs)

    @callback
    def async_service_handler(service: ServiceCall) -> None:
        """Handle logger services."""
        if service.service == SERVICE_SET_DEFAULT_LEVEL:
            set_default_log_level(hass, service.data[ATTR_LEVEL])
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


def _add_log_filter(logger: logging.Logger, patterns: list[re.Pattern]) -> None:
    """Add a Filter to the logger based on a regexp of the filter_str."""

    def filter_func(logrecord: logging.LogRecord) -> bool:
        return not any(p.search(logrecord.getMessage()) for p in patterns)

    logger.addFilter(filter_func)


def _get_logger_class(hass_overrides: dict[str, int]) -> type[logging.Logger]:
    """Create a logger subclass.

    logging.setLoggerClass checks if it is a subclass of Logger and
    so we cannot use partial to inject hass_overrides.
    """

    class HassLogger(logging.Logger):
        """Home Assistant aware logger class."""

        def setLevel(self, level: int | str) -> None:
            """Set the log level unless overridden."""
            if self.name in hass_overrides:
                return

            super().setLevel(level)

        def orig_setLevel(self, level: int | str) -> None:
            """Set the log level."""
            super().setLevel(level)

    return HassLogger
