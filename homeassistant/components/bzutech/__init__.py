"""The BZUTech integration."""

from __future__ import annotations

from bzutech import BzuTech

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up BZUTech from a config entry."""
    bzu_api = BzuTech(entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD])
    if not await bzu_api.start():
        return False

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = bzu_api
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
