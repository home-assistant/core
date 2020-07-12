"""Support for setting the level of logging for components."""
import logging

import voluptuous as vol

from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
import homeassistant.helpers.logging as hass_logging

DOMAIN = "logger"

DATA_LOGGER = "logger"

SERVICE_SET_DEFAULT_LEVEL = "set_default_level"
SERVICE_SET_LEVEL = "set_level"

DEFAULT_LOGSEVERITY = "DEBUG"

LOGGER_DEFAULT = "default"
LOGGER_LOGS = "logs"

ATTR_LEVEL = "level"

_VALID_LOG_LEVEL = vol.All(vol.Upper, vol.In(hass_logging.LOGSEVERITY))

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


async def async_setup(hass, config):
    """Set up the logger component."""
    hass.data[hass_logging.LOGGER_LEVELS] = {}

    @callback
    def set_default_log_level(level):
        """Set the default log level for components."""
        logging.getLogger("").setLevel(hass_logging.LOGSEVERITY[level])

    @callback
    def set_log_levels(logpoints):
        """Set the specified log levels."""
        hass.data[hass_logging.LOGGER_LEVELS].update(logpoints)
        for key, value in logpoints.items():
            logging.getLogger(key).setLevel(hass_logging.LOGSEVERITY[value])

    # Set default log severity
    set_default_log_level(config[DOMAIN].get(LOGGER_DEFAULT, DEFAULT_LOGSEVERITY))

    if LOGGER_LOGS in config[DOMAIN]:
        set_log_levels(config[DOMAIN][LOGGER_LOGS])

    @callback
    def async_service_handler(service):
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
