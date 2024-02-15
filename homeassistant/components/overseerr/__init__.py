"""The Overseerr integration."""
from __future__ import annotations

# import overseerr
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN

# List the platforms that you want to support.
# For your initial PR, limit it to 1 platform.
PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Overseerr from a config entry."""

    # Create Overseerr configuration
    # overseerr_config = overseerr.Configuration(
    #     host=entry.data[CONF_URL], api_key={"apiKey": entry.data[CONF_API_KEY]}
    # )

    # Instantiate overseerr api client
    # overseerr = overseerr.ApiClient(overseerr_config)

    # Instantiate coordinator with use of overseerr api client
    # coordinator = OverseerrCoordinator(hass, overseerr, overseerr_config)

    # Run first refresh of data from coordinator
    # await coordinator.async_config_entry_first_refresh()

    # Set coordinator
    # hass.data.setdefault(DOMAIN, {}, coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
