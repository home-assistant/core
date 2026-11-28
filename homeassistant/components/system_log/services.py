"""Services for the system log integration."""

from enum import StrEnum
import logging

import probatio

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN


class SystemLogService(StrEnum):
    """Store keys for system log services."""

    CLEAR = "clear"
    WRITE = "write"


class SystemLogServiceArgument(StrEnum):
    """Store keys for system log service arguments."""

    MESSAGE = "message"
    LEVEL = "level"
    LOGGER = "logger"


SERVICE_CLEAR_SCHEMA = probatio.Schema({})
SERVICE_WRITE_SCHEMA = probatio.Schema(
    {
        probatio.Required(SystemLogServiceArgument.MESSAGE): cv.string,
        probatio.Optional(SystemLogServiceArgument.LEVEL, default="error"): probatio.In(
            ["debug", "info", "warning", "error", "critical"]
        ),
        probatio.Optional(SystemLogServiceArgument.LOGGER): cv.string,
    }
)


@callback
def _async_clear_service_handler(service: ServiceCall) -> None:
    service.hass.data[DOMAIN].records.clear()


@callback
def _async_write_service_handler(service: ServiceCall) -> None:
    name = service.data.get(SystemLogServiceArgument.LOGGER, f"{__package__}.external")
    logger = logging.getLogger(name)
    level = service.data[SystemLogServiceArgument.LEVEL]
    getattr(logger, level)(service.data[SystemLogServiceArgument.MESSAGE])


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the system log integration."""
    hass.services.async_register(
        DOMAIN,
        SystemLogService.CLEAR,
        _async_clear_service_handler,
        schema=SERVICE_CLEAR_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SystemLogService.WRITE,
        _async_write_service_handler,
        schema=SERVICE_WRITE_SCHEMA,
    )
