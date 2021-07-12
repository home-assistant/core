"""The Weback Cloud Integration integration."""
from __future__ import annotations

from homeassistant.components.weback_cloud.const import DOMAIN, PLATFORMS
from homeassistant.components.weback_cloud.exceptions import InvalidCredentials
from homeassistant.components.weback_cloud.hub import WebackCloudHub
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Weback Cloud devices from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hub = hass.data[DOMAIN][entry.entry_id] = WebackCloudHub(hass, entry.data)
    try:
        await hub.get_devices()
    except (Exception, InvalidCredentials):
        return False
    if hub.devices:
        hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
