"""Support for LIFX."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from aiolifx import products
from aiolifx.aiolifx import Light
from aiolifx.message import Message
import async_timeout
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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
import homeassistant.util.color as color_util

from .const import _LOGGER, DOMAIN, INFRARED_BRIGHTNESS_VALUES_MAP, OVERALL_TIMEOUT

FIX_MAC_FW = AwesomeVersion("3.70")


@callback
def async_entry_is_legacy(entry: ConfigEntry) -> bool:
    """Check if a config entry is the legacy shared one."""
    return entry.unique_id is None or entry.unique_id == DOMAIN


@callback
def async_get_legacy_entry(hass: HomeAssistant) -> ConfigEntry | None:
    """Get the legacy config entry."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if async_entry_is_legacy(entry):
            return entry
    return None


def infrared_brightness_value_to_option(value: int) -> str | None:
    """Convert infrared brightness from value to option."""
    return INFRARED_BRIGHTNESS_VALUES_MAP.get(value, None)


def infrared_brightness_option_to_value(option: str) -> int | None:
    """Convert infrared brightness option to value."""
    option_values = {v: k for k, v in INFRARED_BRIGHTNESS_VALUES_MAP.items()}
    return option_values.get(option, None)


def convert_8_to_16(value: int) -> int:
    """Scale an 8 bit level into 16 bits."""
    return (value << 8) | value


def convert_16_to_8(value: int) -> int:
    """Scale a 16 bit level into 8 bits."""
    return value >> 8


def lifx_features(bulb: Light) -> dict[str, Any]:
    """Return a feature map for this bulb, or a default map if unknown."""
    features: dict[str, Any] = (
        products.features_map.get(bulb.product) or products.features_map[1]
    )
    return features


def find_hsbk(hass: HomeAssistant, **kwargs: Any) -> list[float | int | None] | None:
    """Find the desired color from a number of possible inputs.

    Hue, Saturation, Brightness, Kelvin
    """
    hue, saturation, brightness, kelvin = [None] * 4

    preprocess_turn_on_alternatives(hass, kwargs)

    if ATTR_HS_COLOR in kwargs:
        hue, saturation = kwargs[ATTR_HS_COLOR]
    elif ATTR_RGB_COLOR in kwargs:
        hue, saturation = color_util.color_RGB_to_hs(*kwargs[ATTR_RGB_COLOR])
    elif ATTR_XY_COLOR in kwargs:
        hue, saturation = color_util.color_xy_to_hs(*kwargs[ATTR_XY_COLOR])

    if hue is not None:
        assert saturation is not None
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


def merge_hsbk(
    base: list[float | int | None], change: list[float | int | None]
) -> list[float | int | None]:
    """Copy change on top of base, except when None.

    Hue, Saturation, Brightness, Kelvin
    """
    return [b if c is None else c for b, c in zip(base, change)]


def _get_mac_offset(mac_addr: str, offset: int) -> str:
    octets = [int(octet, 16) for octet in mac_addr.split(":")]
    octets[5] = (octets[5] + offset) % 256
    return ":".join(f"{octet:02x}" for octet in octets)


def _off_by_one_mac(firmware: str) -> bool:
    """Check if the firmware version has the off by one mac."""
    return bool(firmware and AwesomeVersion(firmware) >= FIX_MAC_FW)


def get_real_mac_addr(mac_addr: str, firmware: str) -> str:
    """Increment the last byte of the mac address by one for FW>3.70."""
    return _get_mac_offset(mac_addr, 1) if _off_by_one_mac(firmware) else mac_addr


def formatted_serial(serial_number: str) -> str:
    """Format the serial number to match the HA device registry."""
    return dr.format_mac(serial_number)


def mac_matches_serial_number(mac_addr: str, serial_number: str) -> bool:
    """Check if a mac address matches the serial number."""
    formatted_mac = dr.format_mac(mac_addr)
    return bool(
        formatted_serial(serial_number) == formatted_mac
        or _get_mac_offset(serial_number, 1) == formatted_mac
    )


async def async_execute_lifx(method: Callable) -> Message:
    """Execute a lifx coroutine and wait for a response."""
    future: asyncio.Future[Message] = asyncio.Future()

    def _callback(bulb: Light, message: Message) -> None:
        if not future.done():
            # The future will get canceled out from under
            # us by async_timeout when we hit the OVERALL_TIMEOUT
            future.set_result(message)

    _LOGGER.debug("Sending LIFX command: %s", method)

    method(callb=_callback)
    result = None

    async with async_timeout.timeout(OVERALL_TIMEOUT):
        result = await future

    if result is None:
        raise asyncio.TimeoutError("No response from LIFX bulb")
    return result
