"""The mütesync integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import MutesyncConfigEntry, MutesyncUpdateCoordinator

PLATFORMS = [Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: MutesyncConfigEntry) -> None:
    """Set up mütesync from a config entry."""
    coordinator = MutesyncUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: MutesyncConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
