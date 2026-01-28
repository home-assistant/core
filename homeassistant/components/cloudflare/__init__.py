"""Update the IP addresses of your Cloudflare DNS records."""

from __future__ import annotations

from homeassistant.core import HomeAssistant, ServiceCall

from .const import DOMAIN, SERVICE_UPDATE_RECORDS
from .coordinator import CloudflareConfigEntry, CloudflareCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: CloudflareConfigEntry) -> bool:
    """Set up Cloudflare from a config entry."""
    entry.runtime_data = CloudflareCoordinator(hass, entry)
    await entry.runtime_data.async_config_entry_first_refresh()

    # Since we are not using coordinator for data reads, we need to add dummy listener
    entry.async_on_unload(entry.runtime_data.async_add_listener(lambda: None))

    async def update_records_service(_: ServiceCall) -> None:
        """Set up service for manual trigger."""
        await entry.runtime_data.async_request_refresh()

    hass.services.async_register(DOMAIN, SERVICE_UPDATE_RECORDS, update_records_service)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: CloudflareConfigEntry) -> bool:
    """Unload Cloudflare config entry."""

    return True
