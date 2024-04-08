"""The pyLoad integration."""

from __future__ import annotations

import logging

from aiohttp import CookieJar
from pyloadapi.api import PyLoadAPI
from pyloadapi.exceptions import CannotConnect, InvalidAuth

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import DOMAIN
from .coordinator import PyLoadCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up pyLoad from a config entry."""
    _LOGGER.debug("Setting up entry from config %s", entry.data)
    session = async_create_clientsession(
        hass,
        entry.data.get(CONF_VERIFY_SSL, True),
        cookie_jar=CookieJar(unsafe=True),
    )
    pyload = PyLoadAPI(
        session,
        entry.data[CONF_URL],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )

    try:
        await pyload.login()
    except CannotConnect as e:
        raise ConfigEntryNotReady from e
    except InvalidAuth as e:
        raise ConfigEntryAuthFailed(
            "Authentication failed, please reauthenticate PyLoad."
        ) from e

    coordinator = PyLoadCoordinator(hass, pyload)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
