"""Services for cloudflare."""

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError

from .const import DOMAIN, SERVICE_UPDATE_RECORDS
from .coordinator import CloudflareConfigEntry


def get_config_entry(call: ServiceCall) -> CloudflareConfigEntry:
    """Retrieve current config entry."""
    entries: list[CloudflareConfigEntry] = (
        call.hass.config_entries.async_loaded_entries(DOMAIN)
    )
    if not entries:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="config_entry_not_loaded"
        )
    return entries[0]


async def update_records_service(call: ServiceCall) -> None:
    """Set up service for manual trigger."""
    await get_config_entry(call).runtime_data.async_request_refresh()


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register services."""
    hass.services.async_register(
        DOMAIN,
        SERVICE_UPDATE_RECORDS,
        update_records_service,
    )
