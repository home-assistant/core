"""Support for Hive light devices."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import color as color_util

from . import refresh_system
from .const import ATTR_MODE, DOMAIN
from .entity import HiveEntity

if TYPE_CHECKING:
    from apyhiveapi import Hive

PARALLEL_UPDATES = 0
SCAN_INTERVAL = timedelta(seconds=15)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Hive thermostat based on a config entry."""

    hive: Hive = hass.data[DOMAIN][entry.entry_id]
    devices = hive.session.deviceList.get("light")
    if not devices:
        return
    async_add_entities((HiveDeviceLight(hive, dev) for dev in devices), True)


class HiveDeviceLight(HiveEntity, LightEntity):
    """Hive Active Light Device."""

    _attr_min_color_temp_kelvin = 2700  # 370 Mireds
    _attr_max_color_temp_kelvin = 6500  # 153 Mireds

    def __init__(self, hive: Hive, hive_device: dict[str, Any]) -> None:
        """Initialise hive light."""
        super().__init__(hive, hive_device)
        if self.device["hiveType"] == "warmwhitelight":
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
            self._attr_color_mode = ColorMode.BRIGHTNESS
        elif self.device["hiveType"] == "tuneablelight":
            self._attr_supported_color_modes = {ColorMode.COLOR_TEMP}
            self._attr_color_mode = ColorMode.COLOR_TEMP
        elif self.device["hiveType"] == "colourtuneablelight":
            self._attr_supported_color_modes = {ColorMode.COLOR_TEMP, ColorMode.HS}
            self._attr_color_mode = ColorMode.UNKNOWN

    @refresh_system
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on."""
        new_brightness = None
        new_color_temp = None
        new_color = None
        if ATTR_BRIGHTNESS in kwargs:
            tmp_new_brightness = kwargs[ATTR_BRIGHTNESS]
            percentage_brightness = (tmp_new_brightness / 255) * 100
            new_brightness = int(round(percentage_brightness / 5.0) * 5.0)
            if new_brightness == 0:
                new_brightness = 5
        if ATTR_COLOR_TEMP_KELVIN in kwargs:
            new_color_temp = kwargs[ATTR_COLOR_TEMP_KELVIN]
        if ATTR_HS_COLOR in kwargs:
            get_new_color = kwargs[ATTR_HS_COLOR]
            hue = int(get_new_color[0])
            saturation = int(get_new_color[1])
            new_color = (hue, saturation, 100)

        await self.hive.light.turnOn(
            self.device, new_brightness, new_color_temp, new_color
        )

    @refresh_system
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        await self.hive.light.turnOff(self.device)

    async def async_update(self) -> None:
        """Update all Node data from Hive."""
        await self.hive.session.updateData(self.device)
        self.device = await self.hive.light.getLight(self.device)
        self.attributes.update(self.device.get("attributes", {}))
        self._attr_extra_state_attributes = {
            ATTR_MODE: self.attributes.get(ATTR_MODE),
        }
        self._attr_available = self.device["deviceData"].get("online")
        if self._attr_available:
            self._attr_is_on = self.device["status"]["state"]
            self._attr_brightness = self.device["status"]["brightness"]
            if self.device["hiveType"] == "tuneablelight":
                color_temp = self.device["status"].get("color_temp")
                self._attr_color_temp_kelvin = (
                    None
                    if color_temp is None
                    else color_util.color_temperature_mired_to_kelvin(color_temp)
                )

            if self.device["hiveType"] == "colourtuneablelight":
                if self.device["status"]["mode"] == "COLOUR":
                    rgb = self.device["status"]["hs_color"]
                    self._attr_hs_color = color_util.color_RGB_to_hs(*rgb)
                    self._attr_color_mode = ColorMode.HS
                else:
                    color_temp = self.device["status"].get("color_temp")
                    self._attr_color_temp_kelvin = (
                        None
                        if color_temp is None
                        else color_util.color_temperature_mired_to_kelvin(color_temp)
                    )
                    self._attr_color_mode = ColorMode.COLOR_TEMP
