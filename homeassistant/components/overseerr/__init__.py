"""The Overseerr integration."""
from __future__ import annotations

from overseerr_api import ApiClient, Configuration

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_URL, Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import OverseerrUpdateCoordinator

# List the platforms that you want to support.
# For your initial PR, limit it to 1 platform.
PLATFORMS: list[Platform] = [Platform.SENSOR]


def create_overseerr_client(overseerr_config: Configuration):
    """Create an instance of the Overseerr API client."""
    return ApiClient(overseerr_config)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Overseerr from a config entry."""
    overseerr_config = Configuration(
        host=entry.data[CONF_URL],  # Adjust 'CONF_URL' as necessary
        api_key={
            "apiKey": entry.data[CONF_API_KEY]
        },  # Adjust 'CONF_API_KEY' as necessary
    )

    overseerr_client = await hass.async_add_executor_job(
        create_overseerr_client, overseerr_config
    )
    overseerr_coordinator = OverseerrUpdateCoordinator(hass, overseerr_client)

    # Run first refresh of data from coordinator
    await overseerr_coordinator.async_config_entry_first_refresh()

    # Set coordinator in Home Assistant's data structure for later access
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = overseerr_coordinator

    # Forward the entry setup to the relevant platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
