"""The MirAIe AC integration."""
from __future__ import annotations

import logging

from py_miraie_ac import AuthType, MirAIeAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant

from .const import CONFIG_KEY_USER_ID, DOMAIN

PLATFORMS: list[Platform] = [Platform.CLIMATE]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up MirAIe AC from a config entry."""

    hass.data.setdefault(DOMAIN, {})
    entry.async_on_unload(entry.add_update_listener(update_listener))

    login_id = entry.data[CONFIG_KEY_USER_ID]
    password = entry.data[CONF_PASSWORD]

    api = MirAIeAPI(auth_type=AuthType.MOBILE, login_id=login_id, password=password)
    hass.data[DOMAIN][entry.entry_id] = api

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def update_listener(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Update listener."""
    await hass.config_entries.async_reload(config_entry.entry_id)
