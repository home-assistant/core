"""Light platform for Avea."""

from collections.abc import Callable
from contextlib import suppress
from typing import Any, override

import avea
from bleak.exc import BleakError

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import color as color_util

from . import AveaConfigEntry
from .const import MODEL, UNKNOWN_NAME

UPDATE_EXCEPTIONS = (BleakError, OSError, RuntimeError)
AVEA_MAX_BRIGHTNESS = 4095


def _normalize_name(name: str | None) -> str | None:
    """Return a valid Avea name."""
    if not name or name == UNKNOWN_NAME:
        return None
    return name


def _read_device_info_value(read: Callable[[], str | None]) -> str | None:
    """Read a device information value from an Avea bulb."""
    with suppress(*UPDATE_EXCEPTIONS):
        return _normalize_name(read())
    return None


def _ha_brightness_to_avea(brightness: int) -> int:
    """Convert Home Assistant brightness to Avea brightness."""
    return round((brightness / 255) * AVEA_MAX_BRIGHTNESS)


def _avea_brightness_to_ha(brightness: int) -> int:
    """Convert Avea brightness to Home Assistant brightness."""
    return round(255 * (brightness / AVEA_MAX_BRIGHTNESS))


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AveaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Avea light platform."""
    async_add_entities(
        [AveaLight(entry.runtime_data, entry.data[CONF_ADDRESS])],
        update_before_add=True,
    )


class AveaLight(LightEntity):
    """Representation of an Avea."""

    _attr_color_mode = ColorMode.HS
    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_color_modes = {ColorMode.HS}
    _attr_device_info: DeviceInfo | None = None

    def __init__(self, light: avea.Bulb, address: str) -> None:
        """Initialize an AveaLight."""
        self._light = light
        self._attr_unique_id = address
        self._attr_brightness = light.brightness
        self._last_brightness = 255
        self._device_info_updated = False
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_BLUETOOTH, address)},
            model=MODEL,
        )

    def _update_device_info(self) -> None:
        """Fetch device information from the Avea bulb."""
        device_info = self._attr_device_info
        assert device_info is not None

        manufacturer = _read_device_info_value(self._light.get_manufacturer_name)
        hardware_revision = _read_device_info_value(self._light.get_hardware_revision)
        firmware_version = _read_device_info_value(self._light.get_fw_version)
        serial_number = _read_device_info_value(self._light.get_serial_number)

        if manufacturer:
            device_info.manufacturer = manufacturer
        if hardware_revision:
            device_info.hw_version = hardware_revision
        if firmware_version:
            device_info.sw_version = firmware_version
        if serial_number:
            device_info.serial_number = serial_number

        self._device_info_updated = True

    @override
    def turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on."""
        if not kwargs:
            self._light.set_brightness(_ha_brightness_to_avea(self._last_brightness))
        else:
            if ATTR_BRIGHTNESS in kwargs:
                brightness = kwargs[ATTR_BRIGHTNESS]
                if brightness:
                    self._last_brightness = brightness
                self._light.set_brightness(_ha_brightness_to_avea(brightness))
            if ATTR_HS_COLOR in kwargs:
                rgb = color_util.color_hs_to_RGB(*kwargs[ATTR_HS_COLOR])
                self._light.set_rgb(rgb[0], rgb[1], rgb[2])

    @override
    def turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        self._light.set_brightness(0)
        self._attr_is_on = False
        self._attr_brightness = 0

    def update(self) -> None:
        """Fetch new state data for this light."""
        connected = self._light.connect()

        try:
            if not self._device_info_updated:
                self._update_device_info()
            brightness = self._light.get_brightness()
            rgb_color = self._light.get_rgb()
        finally:
            if connected:
                self._light.disconnect()

        if brightness is not None:
            self._attr_is_on = brightness != 0
            self._attr_brightness = _avea_brightness_to_ha(brightness)
            if self._attr_brightness:
                self._last_brightness = self._attr_brightness
        self._attr_hs_color = color_util.color_RGB_to_hs(*rgb_color)
