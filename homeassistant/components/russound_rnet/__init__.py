"""The Russound RNET integration."""

from __future__ import annotations

import logging

from aiorussound.connection import (
    RussoundConnectionHandler,
    RussoundSerialConnectionHandler,
    RussoundTcpConnectionHandler,
)
from aiorussound.rnet.client import RussoundRNETClient

from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT, CONF_TYPE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DEFAULT_BAUDRATE, DOMAIN, TYPE_TCP
from .coordinator import RussoundRNETConfigEntry, RussoundRNETCoordinator

PLATFORMS = [Platform.MEDIA_PLAYER]

CONFIG_SCHEMA = cv.platform_only_config_schema(DOMAIN)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Russound RNET component."""
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: RussoundRNETConfigEntry
) -> bool:
    """Set up Russound RNET from a config entry."""
    handler: RussoundConnectionHandler
    if entry.data[CONF_TYPE] == TYPE_TCP:
        host = entry.data[CONF_HOST]
        port = entry.data[CONF_PORT]
        handler = RussoundTcpConnectionHandler(host, port)
    else:
        device = entry.data[CONF_DEVICE]
        handler = RussoundSerialConnectionHandler(device, DEFAULT_BAUDRATE)

    client = RussoundRNETClient(handler)
    coordinator = RussoundRNETCoordinator(hass, entry, client)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: RussoundRNETConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
