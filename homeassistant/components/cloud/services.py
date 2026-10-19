"""Services for the Home Assistant Cloud integration."""

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers.service import async_register_admin_service

from .const import DATA_CLOUD, DOMAIN

SERVICE_REMOTE_CONNECT = "remote_connect"
SERVICE_REMOTE_DISCONNECT = "remote_disconnect"


async def _service_handler(service: ServiceCall) -> None:
    """Handle service for cloud."""
    prefs = service.hass.data[DATA_CLOUD].client.prefs
    if service.service == SERVICE_REMOTE_CONNECT:
        await prefs.async_update(remote_enabled=True)
    elif service.service == SERVICE_REMOTE_DISCONNECT:
        await prefs.async_update(remote_enabled=False)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for cloud component."""
    async_register_admin_service(hass, DOMAIN, SERVICE_REMOTE_CONNECT, _service_handler)
    async_register_admin_service(
        hass, DOMAIN, SERVICE_REMOTE_DISCONNECT, _service_handler
    )
