"""The Virtual Remote integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN


type VirtualRemoteConfigEntry = ConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VirtualRemoteConfigEntry,
) -> bool:
    """Set up Virtual Remote from a config entry."""
    await hass.config_entries.async_forward_entry_setups(entry, ["remote"])
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: VirtualRemoteConfigEntry,
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, ["remote"])
