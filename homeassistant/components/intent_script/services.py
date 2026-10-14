"""Services for the intent_script integration."""

from homeassistant.const import SERVICE_RELOAD
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers.service import async_register_admin_service

from .const import DOMAIN
from .helpers import async_reload


async def _handle_reload(service_call: ServiceCall) -> None:
    return await async_reload(service_call.hass, service_call)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the intent_script integration."""
    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_RELOAD,
        _handle_reload,
    )
