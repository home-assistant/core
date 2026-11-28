"""Services for the Huawei LTE integration."""

import logging

import probatio

from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_register_admin_service

from .const import (
    ADMIN_SERVICES,
    DOMAIN,
    SERVICE_RESUME_INTEGRATION,
    SERVICE_SUSPEND_INTEGRATION,
)

_LOGGER = logging.getLogger(__name__)

SERVICE_SCHEMA = probatio.Schema({probatio.Optional(CONF_URL): cv.url})


def _service_handler(service: ServiceCall) -> None:
    """Apply a service.

    We key this using the router URL instead of its unique id / serial number,
    because the latter is not available anywhere in the UI.
    """
    hass = service.hass
    routers = [
        entry.runtime_data for entry in hass.config_entries.async_loaded_entries(DOMAIN)
    ]
    if url := service.data.get(CONF_URL):
        router = next((router for router in routers if router.url == url), None)
    elif not routers:
        _LOGGER.error("%s: no routers configured", service.service)
        return
    elif len(routers) == 1:
        router = routers[0]
    else:
        _LOGGER.error(
            "%s: more than one router configured, must specify one of URLs %s",
            service.service,
            sorted(router.url for router in routers),
        )
        return
    if not router:
        _LOGGER.error("%s: router %s unavailable", service.service, url)
        return

    if service.service == SERVICE_RESUME_INTEGRATION:
        # Login will be handled automatically on demand
        router.suspended = False
        _LOGGER.debug("%s: %s", service.service, "done")
    elif service.service == SERVICE_SUSPEND_INTEGRATION:
        router.logout()
        router.suspended = True
        _LOGGER.debug("%s: %s", service.service, "done")
    else:
        _LOGGER.error("%s: unsupported service", service.service)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Huawei LTE integration."""
    for service in ADMIN_SERVICES:
        async_register_admin_service(
            hass,
            DOMAIN,
            service,
            _service_handler,
            schema=SERVICE_SCHEMA,
        )
