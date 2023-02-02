"""The Waterkotte Heatpump integration."""
from __future__ import annotations

from pywaterkotte.ecotouch import Ecotouch

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Waterkotte Heatpump from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    heatpump = Ecotouch(entry.data.get("host"))

    await hass.async_add_executor_job(
        heatpump.login, entry.data["username"], entry.data["password"]
    )

    hass.data[DOMAIN][entry.entry_id] = heatpump

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
