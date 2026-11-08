"""The Bluetti Bluetooth integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import BluettiBtConfigEntry, PollingCoordinator

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: BluettiBtConfigEntry) -> None:
    """Set up Bluetti Bluetooth from a config entry."""

    coordinator = PollingCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: BluettiBtConfigEntry) -> None:
    """Unload Bluetti Bluetooth config entry."""
    return await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
