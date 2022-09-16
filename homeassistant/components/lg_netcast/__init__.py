"""The lg_netcast component."""
from __future__ import annotations

from typing import Final

from pylgnetcast import LgNetCastClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST, CONF_NAME, Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .media_player import LgTVDevice

PLATFORMS: Final[list[Platform]] = [Platform.MEDIA_PLAYER]


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    host = config_entry.data[CONF_HOST]
    access_token = config_entry.data[CONF_ACCESS_TOKEN]
    name = config_entry.data[CONF_NAME]

    client = LgNetCastClient(host, access_token)
    device = LgTVDevice(client, name, None)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = device

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok
