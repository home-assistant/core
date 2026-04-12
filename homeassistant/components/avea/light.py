"""Light platform for Avea."""

from __future__ import annotations

import logging
from typing import Any

from bleak.exc import BleakError

from homeassistant.components import bluetooth
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
from .const import DOMAIN, MANUFACTURER, MODEL

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AveaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Avea light platform."""
    async_add_entities([AveaLight(hass, entry)], update_before_add=True)


class AveaLight(LightEntity):
    """Representation of an Avea."""

    _attr_color_mode = ColorMode.HS
    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_color_modes = {ColorMode.HS}

    def __init__(self, hass: HomeAssistant, entry: AveaConfigEntry) -> None:
        """Initialize an AveaLight."""
        self.hass = hass
        self._light = entry.runtime_data
        self._address: str = entry.data[CONF_ADDRESS]
        self._attr_unique_id = self._address
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._address)},
            connections={(CONNECTION_BLUETOOTH, self._address)},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name=entry.title,
        )

    def _update_ble_device(self) -> None:
        """Update the library with the latest BLE device if available."""
        if ble_device := bluetooth.async_ble_device_from_address(
            self.hass, self._address, connectable=True
        ):
            self._light.addr = ble_device

    def _sync_update(self) -> tuple[int, tuple[int, int, int]]:
        """Fetch the latest state from the device."""
        if not self._light.connect():
            raise ConnectionError(f"Could not connect to Avea device {self._address}")

        try:
            self._light.get_name()
            brightness = self._light.get_brightness()
            rgb = self._light.get_rgb()
        finally:
            self._light.close()

        return brightness, rgb

    def _sync_turn_on(
        self, brightness: int | None, hs_color: tuple[float, float] | None
    ) -> None:
        """Instruct the light to turn on."""
        if not self._light.connect():
            raise ConnectionError(f"Could not connect to Avea device {self._address}")

        try:
            if brightness is None and hs_color is None:
                self._light.set_brightness(4095)
                return

            if brightness is not None:
                self._light.set_brightness(round((brightness / 255) * 4095))

            if hs_color is not None:
                rgb = color_util.color_hs_to_RGB(*hs_color)
                self._light.set_rgb(rgb[0], rgb[1], rgb[2])
                if brightness is None and not self._attr_is_on:
                    self._light.set_brightness(4095)
        finally:
            self._light.close()

    def _sync_turn_off(self) -> None:
        """Instruct the light to turn off."""
        if not self._light.connect():
            raise ConnectionError(f"Could not connect to Avea device {self._address}")

        try:
            self._light.set_brightness(0)
        finally:
            self._light.close()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on."""
        brightness: int | None = kwargs.get(ATTR_BRIGHTNESS)
        hs_color: tuple[float, float] | None = kwargs.get(ATTR_HS_COLOR)
        self._update_ble_device()

        await self.hass.async_add_executor_job(self._sync_turn_on, brightness, hs_color)

        if not kwargs:
            self._attr_brightness = 255
            self._attr_is_on = True
            return

        if hs_color is not None:
            self._attr_hs_color = hs_color

        if brightness is not None:
            self._attr_brightness = brightness
            self._attr_is_on = brightness > 0
        elif hs_color is not None and not self._attr_is_on:
            self._attr_brightness = 255
            self._attr_is_on = True

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        self._update_ble_device()
        await self.hass.async_add_executor_job(self._sync_turn_off)
        self._attr_is_on = False
        self._attr_brightness = 0

    async def async_update(self) -> None:
        """Fetch new state data for this light."""
        self._update_ble_device()
        try:
            brightness, rgb = await self.hass.async_add_executor_job(self._sync_update)
        except ConnectionError:
            self._attr_available = False
            return
        except BleakError, OSError, RuntimeError:
            _LOGGER.warning(
                "Unexpected error while updating Avea device %s",
                self._address,
                exc_info=True,
            )
            self._attr_available = False
            return

        self._attr_available = True
        self._attr_is_on = brightness != 0
        self._attr_brightness = round(255 * (brightness / 4095))
        self._attr_hs_color = color_util.color_RGB_to_hs(*rgb)
