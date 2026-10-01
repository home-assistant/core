"""Gree IR Remote integration for Home Assistant."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .state import GreeAcState

PLATFORMS = [Platform.CLIMATE, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set up Gree IR from a config entry."""
    entries = hass.data.setdefault(DOMAIN, {})
    entries[entry.entry_id] = GreeAcState()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Unload a Gree IR config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
    hass.data[DOMAIN].pop(entry.entry_id)
    if not hass.data[DOMAIN]:
        del hass.data[DOMAIN]
    return True
