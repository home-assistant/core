"""The Ekey Bionyx integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

PLATFORMS: list[Platform] = [Platform.EVENT]


type EkeyBionyxConfigEntry = ConfigEntry


async def async_setup_entry(hass: HomeAssistant, entry: EkeyBionyxConfigEntry) -> bool:
    """Set up the Ekey Bionyx config entry."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: EkeyBionyxConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
