"""Support for LIFX."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from functools import partial
from typing import Any

from aiolifx import products
from aiolifx.aiolifx import Light
from aiolifx.message import Message
from awesomeversion import AwesomeVersion

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_BRIGHTNESS_PCT,
    ATTR_COLOR_NAME,
    ATTR_COLOR_TEMP,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    ATTR_KELVIN,
    ATTR_RGB_COLOR,
    ATTR_XY_COLOR,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
import homeassistant.util.color as color_util

from .const import (
    _LOGGER,
    DEFAULT_ATTEMPTS,
    DOMAIN,
    INFRARED_BRIGHTNESS_VALUES_MAP,
    OVERALL_TIMEOUT,
)

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

    if (color_name := kwargs.get(ATTR_COLOR_NAME)) is not None:
        try:
            hue, saturation = color_util.color_RGB_to_hs(
                *color_util.color_name_to_rgb(color_name)
            )
        except ValueError:
            _LOGGER.warning(
                "Got unknown color %s, falling back to neutral white", color_name
            )
            hue, saturation = (0, 0)

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

    if ATTR_KELVIN in kwargs:
        _LOGGER.warning(
            "The 'kelvin' parameter is deprecated. Please use 'color_temp_kelvin' for"
            " all service calls"
        )
        kelvin = kwargs.pop(ATTR_KELVIN)
        saturation = 0

    if ATTR_COLOR_TEMP in kwargs:
        kelvin = color_util.color_temperature_mired_to_kelvin(
            kwargs.pop(ATTR_COLOR_TEMP)
        )
        saturation = 0

    if ATTR_COLOR_TEMP_KELVIN in kwargs:
        kelvin = kwargs.pop(ATTR_COLOR_TEMP_KELVIN)
        saturation = 0

    if ATTR_BRIGHTNESS in kwargs:
        brightness = convert_8_to_16(kwargs[ATTR_BRIGHTNESS])

    if ATTR_BRIGHTNESS_PCT in kwargs:
        brightness = convert_8_to_16(round(255 * kwargs[ATTR_BRIGHTNESS_PCT] / 100))

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
    """Execute a lifx callback method and wait for a response."""
    return (
        await async_multi_execute_lifx_with_retries(
            [method], DEFAULT_ATTEMPTS, OVERALL_TIMEOUT
        )
    )[0]


async def async_multi_execute_lifx_with_retries(
    methods: list[Callable], attempts: int, overall_timeout: int
) -> list[Message]:
    """Execute multiple lifx callback methods with retries and wait for a response.

    This functional will the overall timeout by the number of attempts and
    wait for each method to return a result. If we don't get a result
    within the split timeout, we will send all methods that did not generate
    a response again.

    If we don't get a result after all attempts, we will raise an
    asyncio.TimeoutError exception.
    """
    loop = asyncio.get_running_loop()
    futures: list[asyncio.Future] = [loop.create_future() for _ in methods]

    def _callback(
        bulb: Light, message: Message | None, future: asyncio.Future[Message]
    ) -> None:
        if message and not future.done():
            future.set_result(message)

    timeout_per_attempt = overall_timeout / attempts

    for _ in range(attempts):
        for idx, method in enumerate(methods):
            future = futures[idx]
            if not future.done():
                method(callb=partial(_callback, future=future))

        _, pending = await asyncio.wait(futures, timeout=timeout_per_attempt)
        if not pending:
            break

    results: list[Message] = []
    failed: list[str] = []
    for idx, future in enumerate(futures):
        if not future.done() or not (result := future.result()):
            method = methods[idx]
            failed.append(str(getattr(method, "__name__", method)))
        else:
            results.append(result)

    if failed:
        failed_methods = ", ".join(failed)
        raise asyncio.TimeoutError(
            f"{failed_methods} timed out after {attempts} attempts"
        )

    return results
