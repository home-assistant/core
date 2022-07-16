"""Support for Hive light devices."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.util.color as color_util

from . import HiveEntity, refresh_system
from .const import ATTR_MODE, DOMAIN

PARALLEL_UPDATES = 0
SCAN_INTERVAL = timedelta(seconds=15)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Hive thermostat based on a config entry."""

    hive = hass.data[DOMAIN][entry.entry_id]
    devices = hive.session.deviceList.get("light")
    entities = []
    if devices:
        for dev in devices:
            entities.append(HiveDeviceLight(hive, dev))
    async_add_entities(entities, True)


class HiveDeviceLight(HiveEntity, LightEntity):
    """Hive Active Light Device."""

    def __init__(self, hive, hive_device):
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

        self._attr_min_mireds = 153
        self._attr_max_mireds = 370

    @refresh_system
    async def async_turn_on(self, **kwargs):
        """Instruct the light to turn on."""
        new_brightness = None
        new_color_temp = None
        new_color = None
        if ATTR_BRIGHTNESS in kwargs:
            tmp_new_brightness = kwargs.get(ATTR_BRIGHTNESS)
            percentage_brightness = (tmp_new_brightness / 255) * 100
            new_brightness = int(round(percentage_brightness / 5.0) * 5.0)
            if new_brightness == 0:
                new_brightness = 5
        if ATTR_COLOR_TEMP in kwargs:
            tmp_new_color_temp = kwargs.get(ATTR_COLOR_TEMP)
            new_color_temp = round(1000000 / tmp_new_color_temp)
        if ATTR_HS_COLOR in kwargs:
            get_new_color = kwargs.get(ATTR_HS_COLOR)
            hue = int(get_new_color[0])
            saturation = int(get_new_color[1])
            new_color = (hue, saturation, 100)

        await self.hive.light.turnOn(
            self.device, new_brightness, new_color_temp, new_color
        )

    @refresh_system
    async def async_turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        await self.hive.light.turnOff(self.device)

    async def async_update(self):
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
                self._attr_color_temp = self.device["status"].get("color_temp")
            if self.device["hiveType"] == "colourtuneablelight":
                if self.device["status"]["mode"] == "COLOUR":
                    rgb = self.device["status"]["hs_color"]
                    self._attr_hs_color = color_util.color_RGB_to_hs(*rgb)
                    self._attr_color_mode = ColorMode.HS
                else:
                    self._attr_color_temp = self.device["status"].get("color_temp")
                    self._attr_color_mode = ColorMode.COLOR_TEMP
