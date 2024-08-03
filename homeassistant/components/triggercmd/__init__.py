"""The TRIGGERcmd component."""

from __future__ import annotations

from triggercmd import ha

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

PLATFORMS = [
    Platform.SWITCH,
]

type TriggercmdConfigEntry = ConfigEntry[ha.Hub]


async def async_setup_entry(hass: HomeAssistant, entry: TriggercmdConfigEntry) -> bool:
    """Set up TRIGGERcmd from a config entry."""
    entry.runtime_data = ha.Hub(entry.data["token"])

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
