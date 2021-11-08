"""The Renson integration."""
from __future__ import annotations

import rensonVentilationLib.renson as renson

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN

PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Renson from a config entry."""

    renson_api: renson.RensonVentilation = renson.RensonVentilation(entry.data["host"])

    connected = await hass.async_add_executor_job(renson_api.connect)

    if not connected:
        raise ConfigEntryNotReady

    hass.data.setdefault(DOMAIN, {})

    hass.data[DOMAIN][entry.entry_id] = renson_api

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
