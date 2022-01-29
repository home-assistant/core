"""The PECO Outage Counter integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .peco_outage_api import PecoOutageApi

# TODO: Add support for binary sensor to check if actual home is still connected
PLATFORMS: list[str] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up PECO Outage Counter from a config entry."""

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = PecoOutageApi(entry.data["county"])
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
