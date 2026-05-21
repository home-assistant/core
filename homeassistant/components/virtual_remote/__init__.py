"""The Virtual Remote integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

type VirtualRemoteConfigEntry = ConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VirtualRemoteConfigEntry,
) -> bool:
    """Set up Virtual Remote from a config entry."""
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, ["remote"])
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: VirtualRemoteConfigEntry,
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, ["remote"])


async def _async_update_listener(
    hass: HomeAssistant,
    entry: VirtualRemoteConfigEntry,
) -> None:
    """Reload Virtual Remote when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)
