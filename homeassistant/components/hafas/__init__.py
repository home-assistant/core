"""The HaFAS integration."""
from __future__ import annotations

from pyhafas import HafasClient
from pyhafas.profile import DBProfile, VSNProfile

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .config_flow import Profile
from .const import CONF_PROFILE, DOMAIN

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HaFAS from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    client: HafasClient = None
    if entry.data[CONF_PROFILE] == Profile.DB:
        client = HafasClient(DBProfile())
    elif entry.data[CONF_PROFILE] == Profile.VSN:
        client = HafasClient(VSNProfile())

    hass.data[DOMAIN][entry.entry_id] = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
