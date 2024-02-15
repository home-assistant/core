"""The Overseerr integration."""
from __future__ import annotations

from overseerr import ApiClient, Configuration

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_URL, Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import OverseerrCoordinator

# List the platforms that you want to support.
# For your initial PR, limit it to 1 platform.
PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Overseerr from a config entry."""

    # Create Overseerr configuration
    overseerr_config = Configuration(
        host=entry.data[CONF_URL],  # Adjust 'CONF_URL' as necessary
        api_key={
            "apiKey": entry.data[CONF_API_KEY]
        },  # Adjust 'CONF_API_KEY' as necessary
    )

    # Use 'async with' to ensure proper handling of the ApiClient lifecycle
    async with ApiClient(overseerr_config) as overseerr_api_client:
        # Instantiate coordinator with the use of overseerr api client
        coordinator = OverseerrCoordinator(hass, overseerr_api_client, overseerr_config)

        # Run first refresh of data from coordinator
        await coordinator.async_config_entry_first_refresh()

    # Since the coordinator was created within the async with block, make sure it's accessible outside.
    # If the coordinator needs the API client beyond initial setup, consider restructuring to ensure the client remains available as needed.

    # Set coordinator in Home Assistant's data structure for later access
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    # Forward the entry setup to the relevant platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
