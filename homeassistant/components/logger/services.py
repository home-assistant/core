"""Services for the logger integration."""

import probatio

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_register_admin_service

from .const import ATTR_LEVEL, DOMAIN, SERVICE_SET_DEFAULT_LEVEL, SERVICE_SET_LEVEL
from .helpers import VALID_LOG_LEVEL, set_default_log_level, set_log_levels

SERVICE_SET_DEFAULT_LEVEL_SCHEMA = probatio.Schema({ATTR_LEVEL: VALID_LOG_LEVEL})
SERVICE_SET_LEVEL_SCHEMA = probatio.Schema({cv.string: VALID_LOG_LEVEL})


@callback
def _async_service_handler(service: ServiceCall) -> None:
    """Handle logger services."""
    if service.service == SERVICE_SET_DEFAULT_LEVEL:
        set_default_log_level(service.hass, service.data[ATTR_LEVEL])
    else:
        set_log_levels(service.hass, service.data)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the logger services."""

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_SET_DEFAULT_LEVEL,
        _async_service_handler,
        schema=SERVICE_SET_DEFAULT_LEVEL_SCHEMA,
    )

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_SET_LEVEL,
        _async_service_handler,
        schema=SERVICE_SET_LEVEL_SCHEMA,
    )
