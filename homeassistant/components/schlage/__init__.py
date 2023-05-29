"""The Schlage integration."""
from __future__ import annotations

import pyschlage

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN

PLATFORMS: list[Platform] = [Platform.LOCK]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Schlage from a config entry."""

    hass.data.setdefault(DOMAIN, {})
    auth = await hass.async_add_executor_job(
        pyschlage.Auth, entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD]
    )
    hass.data[DOMAIN][entry.entry_id] = pyschlage.Schlage(auth)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
