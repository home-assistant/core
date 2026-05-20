"""The iNet Radio integration."""

from __future__ import annotations

import logging

from inet_control import RadioManager

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
INET_KEY: HassKey[RadioManager] = HassKey(DOMAIN)

type INetConfigEntry = ConfigEntry[RadioManager]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the iNet Radio integration."""
    manager = RadioManager()
    await manager.start()
    hass.data[INET_KEY] = manager
    return True


async def async_setup_entry(hass: HomeAssistant, entry: INetConfigEntry) -> bool:
    """Set up iNet Radio from a config entry."""
    manager = hass.data[INET_KEY]
    host = entry.data[CONF_HOST]

    try:
        await manager.connect(host, timeout=5.0)
    except (TimeoutError, OSError) as err:
        raise ConfigEntryNotReady(f"Cannot connect to radio at {host}") from err

    entry.runtime_data = manager
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: INetConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
