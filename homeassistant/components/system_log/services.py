"""Services for the system log integration."""

import logging

import probatio

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_LEVEL,
    CONF_LOGGER,
    CONF_MESSAGE,
    DOMAIN,
    SERVICE_CLEAR,
    SERVICE_WRITE,
)

SERVICE_CLEAR_SCHEMA = probatio.Schema({})
SERVICE_WRITE_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_MESSAGE): cv.string,
        probatio.Optional(CONF_LEVEL, default="error"): probatio.In(
            ["debug", "info", "warning", "error", "critical"]
        ),
        probatio.Optional(CONF_LOGGER): cv.string,
    }
)


@callback
def _async_clear_service_handler(service: ServiceCall) -> None:
    service.hass.data[DOMAIN].records.clear()


@callback
def _async_write_service_handler(service: ServiceCall) -> None:
    name = service.data.get(CONF_LOGGER, f"{__package__}.external")
    logger = logging.getLogger(name)
    level = service.data[CONF_LEVEL]
    getattr(logger, level)(service.data[CONF_MESSAGE])


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the system log integration."""
    hass.services.async_register(
        DOMAIN, SERVICE_CLEAR, _async_clear_service_handler, schema=SERVICE_CLEAR_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_WRITE, _async_write_service_handler, schema=SERVICE_WRITE_SCHEMA
    )
