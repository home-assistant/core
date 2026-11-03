"""The Zeversolar integration."""

from homeassistant.core import HomeAssistant

from .const import PLATFORMS
from .coordinator import ZeversolarConfigEntry, ZeversolarCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ZeversolarConfigEntry) -> None:
    """Set up Zeversolar from a config entry."""
    coordinator = ZeversolarCoordinator(hass=hass, entry=entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: ZeversolarConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
