"""The Flipper IR integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_COMMANDS

PLATFORMS: list[Platform] = [Platform.BUTTON]

type FlipperIRConfigEntry = ConfigEntry[list[dict[str, str]]]


async def async_setup_entry(hass: HomeAssistant, entry: FlipperIRConfigEntry) -> bool:
    """Set up Flipper IR from a config entry."""
    entry.runtime_data = list(entry.data.get(CONF_COMMANDS, []))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: FlipperIRConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
