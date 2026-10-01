"""Gree IR Remote integration for Home Assistant."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .state import GreeAcState

type GreeInfraredConfigEntry = ConfigEntry[GreeAcState]

PLATFORMS = [Platform.CLIMATE, Platform.SWITCH, Platform.SELECT, Platform.NUMBER]


async def async_setup_entry(
    hass: HomeAssistant, entry: GreeInfraredConfigEntry
) -> bool:
    """Set up Gree IR from a config entry."""
    entry.runtime_data = GreeAcState()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: GreeInfraredConfigEntry
) -> bool:
    """Unload a Gree IR config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
