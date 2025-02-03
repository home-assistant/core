"""The Gryf Smart integration."""

from __future__ import annotations

import logging

from pygryfsmart.api import GryfApi

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.typing import ConfigType

from .const import CONF_API, CONF_COMMUNICATION, CONF_DEVICE_DATA, CONF_PORT, DOMAIN
from .schema import CONFIG_SCHEMA as SCHEMA

CONFIG_SCHEMA = SCHEMA

_PLATFORMS: list[Platform] = [
    Platform.LIGHT,
    # Platform.BINARY_SENSOR,
    # Platform.SENSOR
    # Platform.CLIMATE,
    # Platform.COVER,
    # Platform.SWITCH,
    # Platform.LOCK
]

_LOGGER = logging.getLogger(__name__)


async def async_setup(
    hass: HomeAssistant,
    config: ConfigType,
) -> bool:
    """Set up the Gryf Smart Integration."""

    if config.get(DOMAIN) is None:
        return True

    try:
        api = GryfApi(config[DOMAIN][CONF_PORT])
        await api.start_connection()
    except ConnectionError:
        _LOGGER.error("Unable to connect: %s", ConnectionError)
        return False

    hass.data[DOMAIN] = config.get(DOMAIN)
    hass.data[DOMAIN][CONF_API] = api

    await async_load_platform(hass, Platform.LIGHT, DOMAIN, None, config)

    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Config flow for Gryf Smart Integration."""

    try:
        api = GryfApi(entry.data[CONF_COMMUNICATION][CONF_PORT])
        await api.start_connection()
    except ConnectionError:
        raise ConfigEntryNotReady("Unable to connect with device") from ConnectionError

    entry.runtime_data = {}
    entry.runtime_data[CONF_API] = api
    entry.runtime_data[CONF_DEVICE_DATA] = {
        "identifiers": {(DOMAIN, "Gryf Smart", entry.unique_id)},
        "name": f"Gryf Smart {entry.unique_id}",
        "manufacturer": "Gryf Smart",
        "model": "serial",
        "sw_version": "1.0.0",
        "hw_version": "1.0.0",
    }

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
