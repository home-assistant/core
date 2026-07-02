"""The Disneyland Paris Integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import DisneylandParisConfigEntry, DisneylandParisCoordinator

PLATFORMS = [
    Platform.SENSOR,
]


async def async_setup_entry(
    hass: HomeAssistant, entry: DisneylandParisConfigEntry
) -> bool:
    """Set up Disneyland Paris as config entry."""

    coordinator = DisneylandParisCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: DisneylandParisConfigEntry
) -> bool:
    """Unload a Disneyland Paris config entry."""

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
