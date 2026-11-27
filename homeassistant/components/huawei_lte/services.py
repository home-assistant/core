"""Services for the Huawei LTE integration."""

from enum import StrEnum
import logging

import probatio

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_register_admin_service

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class HuaweiLteService(StrEnum):
    """Store keys for Huawei LTE services."""

    RESUME_INTEGRATION = "resume_integration"
    SUSPEND_INTEGRATION = "suspend_integration"


class HuaweiLteServiceArgument(StrEnum):
    """Store keys for Huawei LTE service arguments."""

    URL = "url"


SERVICE_SCHEMA = probatio.Schema(
    {probatio.Optional(HuaweiLteServiceArgument.URL): cv.url}
)


def _service_handler(service: ServiceCall) -> None:
    """Apply a service.

    We key this using the router URL instead of its unique id / serial number,
    because the latter is not available anywhere in the UI.
    """
    hass = service.hass
    routers = [
        entry.runtime_data for entry in hass.config_entries.async_loaded_entries(DOMAIN)
    ]
    if url := service.data.get(HuaweiLteServiceArgument.URL):
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

    if service.service == HuaweiLteService.RESUME_INTEGRATION:
        # Login will be handled automatically on demand
        router.suspended = False
        _LOGGER.debug("%s: %s", service.service, "done")
    elif service.service == HuaweiLteService.SUSPEND_INTEGRATION:
        router.logout()
        router.suspended = True
        _LOGGER.debug("%s: %s", service.service, "done")
    else:
        _LOGGER.error("%s: unsupported service", service.service)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Huawei LTE integration."""
    for service in HuaweiLteService:
        async_register_admin_service(
            hass,
            DOMAIN,
            service,
            _service_handler,
            schema=SERVICE_SCHEMA,
        )
