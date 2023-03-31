"""The myStrom integration."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
from pymystrom.bulb import MyStromBulb
from pymystrom.exceptions import MyStromConnectionError
from pymystrom.switch import MyStromSwitch

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN

PLATFORMS: list[Platform] = [Platform.SWITCH]

_LOGGER = logging.getLogger(__name__)


async def get_device_info(host: str) -> dict[str, Any]:
    """Get the device info of a myStrom device."""
    async with aiohttp.ClientSession() as session:
        async with session.get(f"http://{host}/api/v1/info") as response:
            if response.status != 200:
                async with session.get(f"http://{host}/info.json") as response:
                    if response.status != 200:
                        raise MyStromConnectionError()
            content_type = response.headers.get("Content-Type", "")
            if "application/json" in content_type:
                return await response.json()
            raise MyStromConnectionError()


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up myStrom from a config entry."""
    host = entry.data[CONF_HOST]
    device = None
    try:
        info = await get_device_info(host)
        device_type = info["type"]
        if device_type in [101, 106, 107]:
            device = MyStromSwitch(host)
            await device.get_state()
        elif device_type == 102:
            mac = info["mac"]
            device = MyStromBulb(host, mac)
            await device.get_state()
            if device.bulb_type not in ["rgblamp", "strip"]:
                _LOGGER.error(
                    "Device %s (%s) is not a myStrom bulb nor myStrom LED Strip",
                    host,
                    mac,
                )
                device = None

    except MyStromConnectionError as err:
        _LOGGER.error("No route to myStrom plug: %s", host)
        raise ConfigEntryNotReady() from err

    if device:
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
            "device": device,
            "info": info,
        }
        hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
