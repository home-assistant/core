"""The Russound RNET integration."""

from __future__ import annotations

import logging

from aiorussound import RussoundTcpConnectionHandler
from aiorussound.connection import RussoundSerialConnectionHandler
from aiorussound.rnet.client import RussoundRNETClient

from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT, CONF_TYPE, Platform
from homeassistant.core import HomeAssistant

from .const import CONF_BAUDRATE, TYPE_TCP
from .coordinator import RussoundRNETConfigEntry, RussoundRNETCoordinator

PLATFORMS = [Platform.MEDIA_PLAYER]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: RussoundRNETConfigEntry
) -> bool:
    """Set up Russound RNET from a config entry."""
    if entry.data[CONF_TYPE] == TYPE_TCP:
        host = entry.data[CONF_HOST]
        port = entry.data[CONF_PORT]
        handler = RussoundTcpConnectionHandler(host, port)
    else:
        device = entry.data[CONF_DEVICE]
        baudrate = entry.data[CONF_BAUDRATE]
        handler = RussoundSerialConnectionHandler(device, baudrate)

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
