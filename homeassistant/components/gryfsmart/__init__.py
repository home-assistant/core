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

from .const import CONF_API, CONF_COMMUNICATION, CONF_PORT, DOMAIN
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

    hass.data[DOMAIN] = config.get(DOMAIN)

    if config.get(DOMAIN) is None:
        return True

    _LOGGER.debug("%s", config.get(DOMAIN))

    try:
        api = GryfApi(config[DOMAIN][CONF_COMMUNICATION][CONF_PORT])
        await api.start_connection()
    except ConnectionError:
        raise ConfigEntryNotReady("Unable to connect with device") from ConnectionError

    hass.data[DOMAIN][CONF_API] = api

    lights_config = config.get(Platform.LIGHT, {})

    await async_load_platform(hass, Platform.LIGHT, DOMAIN, lights_config, config)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Config flow for Gryf Smart Integration."""
    try:
        api = GryfApi(entry.data[CONF_COMMUNICATION][CONF_PORT])
        await api.start_connection()
    except ConnectionError:
        _LOGGER.error("Unable to connect: %s", ConnectionError)
        return False

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][CONF_API] = api
    entry.runtime_data = api

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    hass.data[DOMAIN][entry.entry_id] = entry.data
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
