"""The pyLoad integration."""

from __future__ import annotations

import logging

from aiohttp import CookieJar
from pyloadapi import PyLoadAPI
from yarl import URL

from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PATH,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .coordinator import PyLoadConfigEntry, PyLoadCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.BUTTON, Platform.SENSOR, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: PyLoadConfigEntry) -> bool:
    """Set up pyLoad from a config entry."""

    session = async_create_clientsession(
        hass,
        verify_ssl=entry.data[CONF_VERIFY_SSL],
        cookie_jar=CookieJar(unsafe=True),
    )
    url = URL.build(
        scheme="https" if entry.data[CONF_SSL] else "http",
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        path=entry.data[CONF_PATH],
    )
    pyloadapi = PyLoadAPI(
        session,
        api_url=url,
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
    )

    coordinator = PyLoadCoordinator(hass, entry, pyloadapi)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: PyLoadConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: PyLoadConfigEntry) -> bool:
    """Migrate config entry."""
    _LOGGER.debug(
        "Migrating configuration from version %s.%s", entry.version, entry.minor_version
    )

    if entry.version == 1 and entry.minor_version == 0:
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_PATH: "/"}, minor_version=1, version=1
        )

    _LOGGER.debug(
        "Migration to configuration version %s.%s successful",
        entry.version,
        entry.minor_version,
    )
    return True
