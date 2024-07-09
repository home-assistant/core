"""The TRIGGERcmd component."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import hub

PLATFORMS: list[str] = ["switch"]


@dataclass
class TriggercmdData:
    """TRIGGERcmd data."""

    hub: hub.Hub


type TriggercmdConfigEntry = ConfigEntry[TriggercmdData]


async def async_setup_entry(hass: HomeAssistant, entry: TriggercmdConfigEntry) -> bool:
    """Set up TRIGGERcmd from a config entry."""
    entry.runtime_data = TriggercmdData(hub.Hub(hass, entry.data["token"]))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
