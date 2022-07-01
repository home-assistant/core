"""Support for LIFX."""

from __future__ import annotations

import asyncio
from typing import Any

import aiolifx as aiolifx_module
from aiolifx.aiolifx import Device
from aiolifx.message import Message
import aiolifx_effects as aiolifx_effects_module
from awesomeversion import AwesomeVersion

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    ATTR_RGB_COLOR,
    ATTR_XY_COLOR,
    preprocess_turn_on_alternatives,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
import homeassistant.util.color as color_util

from .const import DOMAIN

FIX_MAC_FW = AwesomeVersion("3.70")


@callback
def async_entry_is_legacy(entry: ConfigEntry) -> bool:
    """Check if a config entry is the legacy shared one."""
    return entry.unique_id is None or entry.unique_id == DOMAIN


def convert_8_to_16(value):
    """Scale an 8 bit level into 16 bits."""
    return (value << 8) | value


def convert_16_to_8(value):
    """Scale a 16 bit level into 8 bits."""
    return value >> 8


def aiolifx():
    """Return the aiolifx module."""
    return aiolifx_module


def aiolifx_effects():
    """Return the aiolifx_effects module."""
    return aiolifx_effects_module


def lifx_features(bulb):
    """Return a feature map for this bulb, or a default map if unknown."""
    return aiolifx().products.features_map.get(
        bulb.product
    ) or aiolifx().products.features_map.get(1)


def find_hsbk(hass, **kwargs):
    """Find the desired color from a number of possible inputs."""
    hue, saturation, brightness, kelvin = [None] * 4

    preprocess_turn_on_alternatives(hass, kwargs)

    if ATTR_HS_COLOR in kwargs:
        hue, saturation = kwargs[ATTR_HS_COLOR]
    elif ATTR_RGB_COLOR in kwargs:
        hue, saturation = color_util.color_RGB_to_hs(*kwargs[ATTR_RGB_COLOR])
    elif ATTR_XY_COLOR in kwargs:
        hue, saturation = color_util.color_xy_to_hs(*kwargs[ATTR_XY_COLOR])

    if hue is not None:
        hue = int(hue / 360 * 65535)
        saturation = int(saturation / 100 * 65535)
        kelvin = 3500

    if ATTR_COLOR_TEMP in kwargs:
        kelvin = int(
            color_util.color_temperature_mired_to_kelvin(kwargs[ATTR_COLOR_TEMP])
        )
        saturation = 0

    if ATTR_BRIGHTNESS in kwargs:
        brightness = convert_8_to_16(kwargs[ATTR_BRIGHTNESS])

    hsbk = [hue, saturation, brightness, kelvin]
    return None if hsbk == [None] * 4 else hsbk


def merge_hsbk(base, change):
    """Copy change on top of base, except when None."""
    if change is None:
        return None
    return [b if c is None else c for b, c in zip(base, change)]


class AwaitAioLIFX:
    """Wait for an aiolifx callback and return the message."""

    def __init__(self):
        """Initialize the wrapper."""
        self.message: Message | None = None
        self.event = asyncio.Event()

    @callback
    def callback(self, bulb: Device, message: Message) -> None:
        """Handle responses."""
        self.message = message
        self.event.set()

    async def wait(self, method: Any) -> Message | None:
        """Call an aiolifx method and wait for its response."""
        self.message = None
        self.event.clear()
        method(callb=self.callback)

        await self.event.wait()
        return self.message


def get_real_mac_addr(mac_addr: str, host_firmware_version: str):
    """Increment the last byte of the mac address by one for FW>3.70."""
    if host_firmware_version and AwesomeVersion(host_firmware_version) >= FIX_MAC_FW:
        octets = [int(octet, 16) for octet in mac_addr.split(":")]
        octets[5] = (octets[5] + 1) % 256
        return ":".join(f"{octet:02x}" for octet in octets)
    return mac_addr
