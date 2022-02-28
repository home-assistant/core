"""The laundrify integration."""
from __future__ import annotations

from laundrify_aio import LaundrifyAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up laundrify from a config entry."""
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "api": LaundrifyAPI(entry.data[CONF_ACCESS_TOKEN])
    }

    entry.async_on_unload(entry.add_update_listener(options_update_listener))

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def options_update_listener(hass: HomeAssistant, config_entry: ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
