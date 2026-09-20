"""The Bluetti BT integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import BluettiBtConfigEntry, PollingCoordinator

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: BluettiBtConfigEntry) -> bool:
    """Set up Bluetti BT from a config entry."""

    # Setup coordinator
    coordinator = PollingCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    # Setup platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: BluettiBtConfigEntry) -> bool:
    """Unload Bluetti BT config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
