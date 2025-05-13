"""Support for Amber Electric."""

import amberelectric

from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)

from .const import CONF_SITE_ID, DOMAIN, PLATFORMS
from .coordinator import AmberConfigEntry, AmberUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: AmberConfigEntry) -> bool:
    """Set up Amber Electric from a config entry."""
    configuration = amberelectric.Configuration(access_token=entry.data[CONF_API_TOKEN])
    api_client = amberelectric.ApiClient(configuration)
    api_instance = amberelectric.AmberApi(api_client)
    site_id = entry.data[CONF_SITE_ID]

    coordinator = AmberUpdateCoordinator(hass, entry, api_instance, site_id)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def handle_get_forecasts(call: ServiceCall) -> ServiceResponse:
        return coordinator.get_forecasts()

    hass.services.async_register(DOMAIN, "get_forecasts", handle_get_forecasts, {}, supports_response=SupportsResponse.ONLY)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AmberConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
