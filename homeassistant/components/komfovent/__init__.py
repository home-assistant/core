"""The Komfovent integration."""
from __future__ import annotations

import komfovent_api

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN

PLATFORMS: list[Platform] = [Platform.CLIMATE]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Komfovent from a config entry."""
    host = entry.data[CONF_HOST]
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    _, credentials = komfovent_api.get_credentials(host, username, password)
    result, settings = await komfovent_api.get_settings(credentials)
    if result != komfovent_api.KomfoventConnectionResult.SUCCESS:
        raise ConfigEntryNotReady(f"Unable to connect to {host}: {result}")

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = (credentials, settings)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
