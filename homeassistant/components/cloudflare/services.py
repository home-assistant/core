"""Services for cloudflare."""

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import service

from .const import DOMAIN, SERVICE_UPDATE_RECORDS
from .coordinator import CloudflareConfigEntry


async def update_records_service(call: ServiceCall) -> None:
    """Set up service for manual trigger."""
    entry: CloudflareConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, None
    )
    await entry.runtime_data.async_request_refresh()


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register services."""
    hass.services.async_register(
        DOMAIN,
        SERVICE_UPDATE_RECORDS,
        update_records_service,
    )
