"""The myStrom integration."""

from __future__ import annotations

import asyncio
import logging

import pymystrom
from pymystrom.bulb import MyStromBulb
from pymystrom.exceptions import MyStromConnectionError
from pymystrom.pir import MyStromPir
from pymystrom.switch import MyStromSwitch

from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .models import MyStromConfigEntry, MyStromData

PLATFORMS_PLUGS = [Platform.SENSOR, Platform.SWITCH]
PLATFORMS_BULB = [Platform.LIGHT]
PLATFORMS_MOTION_SENSOR = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def _async_get_device_state(
    device: MyStromSwitch | MyStromBulb | MyStromPir, ip_address: str
) -> None:
    try:
        if isinstance(device, MyStromPir):
            await asyncio.gather(
                device.get_light(), device.get_motion(), device.get_temperatures()
            )
        else:
            await device.get_state()
    except MyStromConnectionError as err:
        _LOGGER.error("No route to myStrom plug: %s", ip_address)
        raise ConfigEntryNotReady from err


def _get_mystrom_bulb(host: str, mac: str) -> MyStromBulb:
    return MyStromBulb(host, mac)


def _get_mystrom_pir(host: str) -> MyStromPir:
    return MyStromPir(host)


def _get_mystrom_switch(host: str) -> MyStromSwitch:
    return MyStromSwitch(host)


async def async_setup_entry(hass: HomeAssistant, entry: MyStromConfigEntry) -> bool:
    """Set up myStrom from a config entry."""
    host = entry.data[CONF_HOST]
    try:
        info = await pymystrom.get_device_info(host)
    except MyStromConnectionError as err:
        _LOGGER.error("No route to myStrom plug: %s", host)
        raise ConfigEntryNotReady from err

    info.setdefault("type", 101)

    device_type = info["type"]
    if device_type in [101, 106, 107, 120]:
        device = _get_mystrom_switch(host)
        platforms = PLATFORMS_PLUGS
        await _async_get_device_state(device, info["ip"])
    elif device_type in [102, 105]:
        mac = info["mac"]
        device = _get_mystrom_bulb(host, mac)
        platforms = PLATFORMS_BULB
        await _async_get_device_state(device, info["ip"])
        if device.bulb_type not in ["rgblamp", "strip"]:
            _LOGGER.error(
                "Device %s (%s) is not a myStrom bulb nor myStrom LED Strip",
                host,
                mac,
            )
            return False
    elif device_type == 110:
        device = _get_mystrom_pir(host)
        platforms = PLATFORMS_MOTION_SENSOR
        await _async_get_device_state(device, info["ip"])
    else:
        _LOGGER.error("Unsupported myStrom device type: %s", device_type)
        return False

    entry.runtime_data = MyStromData(
        device=device,
        info=info,
    )
    await hass.config_entries.async_forward_entry_setups(entry, platforms)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: MyStromConfigEntry) -> bool:
    """Unload a config entry."""
    device_type = entry.runtime_data.info["type"]
    platforms = []
    if device_type in [101, 106, 107, 120]:
        platforms.extend(PLATFORMS_PLUGS)
    elif device_type in [102, 105]:
        platforms.extend(PLATFORMS_BULB)
    elif device_type == 110:
        platforms.extend(PLATFORMS_MOTION_SENSOR)
    return await hass.config_entries.async_unload_platforms(entry, platforms)
