"""Services for cloudflare."""

from enum import StrEnum

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import service

from .const import DOMAIN
from .coordinator import CloudflareConfigEntry


class CloudflareService(StrEnum):
    """Store keys for Cloudflare services."""

    UPDATE_RECORDS = "update_records"


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
        CloudflareService.UPDATE_RECORDS,
        update_records_service,
    )
