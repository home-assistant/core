"""The Happiest Baby Snoo integration."""

from __future__ import annotations

import asyncio
import logging

from python_snoo.exceptions import InvalidSnooAuth, SnooAuthException, SnooDeviceError
from python_snoo.snoo import Snoo

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import SnooConfigEntry, SnooCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.EVENT,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: SnooConfigEntry) -> bool:
    """Set up Happiest Baby Snoo from a config entry."""

    snoo = Snoo(
        email=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        clientsession=async_get_clientsession(hass),
    )

    try:
        await snoo.authorize()
    except (SnooAuthException, InvalidSnooAuth) as ex:
        raise ConfigEntryNotReady from ex
    try:
        devices = await snoo.get_devices()
    except SnooDeviceError as ex:
        raise ConfigEntryNotReady from ex
    coordinators: dict[str, SnooCoordinator] = {}
    tasks = []
    for device in devices:
        coordinators[device.serialNumber] = SnooCoordinator(hass, device, snoo)
        tasks.append(coordinators[device.serialNumber].setup())
    await asyncio.gather(*tasks)
    entry.runtime_data = coordinators
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: SnooConfigEntry) -> bool:
    """Unload a config entry."""
    disconnects = await asyncio.gather(
        *(coordinator.snoo.disconnect() for coordinator in entry.runtime_data.values()),
        return_exceptions=True,
    )
    for disconnect in disconnects:
        if isinstance(disconnect, Exception):
            _LOGGER.warning(
                "Failed to disconnect a logger with exception: %s", disconnect
            )
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
