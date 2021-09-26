"""The Renson Endura Delta integration."""
from __future__ import annotations

import rensonVentilationLib.renson as renson

from homeassistant.components.renson_endura_delta.config_flow import CannotConnect
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Renson Endura Delta from a config entry."""

    rensonApi: renson.RensonVentilation = renson.RensonVentilation(entry.data["host"])

    connected = await hass.async_add_executor_job(rensonApi.connect)

    if not connected:
        raise CannotConnect

    hass.data.setdefault(DOMAIN, {})

    hass.data[DOMAIN][entry.entry_id] = rensonApi

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
