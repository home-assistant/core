"""The Ambient Weather Network integration."""

from aioambient.open_api import OpenAPI

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import AmbientNetworkConfigEntry, AmbientNetworkDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, entry: AmbientNetworkConfigEntry
) -> None:
    """Set up the Ambient Weather Network from a config entry."""

    api = OpenAPI()
    coordinator = AmbientNetworkDataUpdateCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(
    hass: HomeAssistant, entry: AmbientNetworkConfigEntry
) -> None:
    """Unload a config entry."""

    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
