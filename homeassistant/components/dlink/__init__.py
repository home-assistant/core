"""The D-Link Power Plug integration."""
from __future__ import annotations

from pyW215.pyW215 import SmartPlug

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_USE_LEGACY_PROTOCOL, DOMAIN
from .data import SmartPlugData

PLATFORMS = [Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up D-Link Power Plug from a config entry."""
    smartplug = await hass.async_add_executor_job(
        SmartPlug,
        entry.data[CONF_HOST],
        entry.data[CONF_PASSWORD],
        entry.data[CONF_USERNAME],
        entry.data[CONF_USE_LEGACY_PROTOCOL],
    )
    if not smartplug.authenticated and smartplug.use_legacy_protocol:
        raise ConfigEntryNotReady("Cannot connect/authenticate")

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = SmartPlugData(smartplug)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
