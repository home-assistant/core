"""Business logic for light entity."""
from __future__ import annotations

import json
import logging
from typing import Any

from homeassistant.components.light import LightEntity, ColorMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MQTT_CLIENT_INSTANCE, \
    EVENT_ENTITY_REGISTER, EVENT_ENTITY_STATE_UPDATE, CACHE_ENTITY_STATE_UPDATE_KEY_DICT

_LOGGER = logging.getLogger(__name__)

COMPONENT = "light"

LIGHT_MIN_KELVIN = 2700

LIGHT_MAX_KELVIN = 6500


async def async_setup_entry(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> None:
    """This method is executed after the integration is initialized to create an event listener,
    which is used to create a sub-device"""

    async def async_discover(config_payload):
        try:
            async_add_entities([CustomLight(hass, config_payload, config_entry)])
        except Exception:
            raise

    async_dispatcher_connect(
        hass, EVENT_ENTITY_REGISTER.format(COMPONENT), async_discover
    )


class CustomLight(LightEntity):
    """Custom entity class to handle business logic related to lights"""

    def turn_on(self, **kwargs: Any) -> None:
        pass

    def turn_off(self, **kwargs: Any) -> None:
        pass

    should_poll = False

    def __init__(self, hass: HomeAssistant, config: dict, config_entry: ConfigEntry) -> None:
        self._attr_unique_id = config["unique_id"]

        self._attr_entity_id = config["unique_id"]

        self._attr_name = config["name"]

        self._attr_max_mireds = LIGHT_MAX_KELVIN

        self._attr_min_mireds = LIGHT_MIN_KELVIN

        self.on_off = False

        self.is_group = config["is_group"]

        self._attr_supported_color_modes: set[ColorMode] = set()

        self._attr_supported_color_modes.add(ColorMode.COLOR_TEMP)

        if self.is_group:
            self.room = int(config["room"])
            self.subgroup = int(config["subgroup"])
            self._attr_color_mode = ColorMode.RGB
            self._attr_supported_color_modes.add(ColorMode.RGB)
        else:
            self.sn = config["sn"]
            if "rgb" in config:
                self._attr_color_mode = ColorMode.RGB
                self._attr_supported_color_modes.add(ColorMode.RGB)

        self._attr_color_mode = ColorMode.COLOR_TEMP

        self.hass = hass

        self.config_entry = config_entry

        self.update_state(config)

        async def async_discover(data: dict):
            try:
                self.update_state(data)
                self.async_write_ha_state()
            except Exception:
                raise

        """Add a device state change event listener, and execute the specified method when the device state changes. 
        Note: It is necessary to determine whether an event listener has been added here to avoid repeated additions."""
        key = EVENT_ENTITY_STATE_UPDATE.format(self.unique_id)
        if key not in hass.data[CACHE_ENTITY_STATE_UPDATE_KEY_DICT]:
            hass.data[CACHE_ENTITY_STATE_UPDATE_KEY_DICT][key] = async_dispatcher_connect(
                hass, key, async_discover
            )

    @property
    def device_info(self) -> DeviceInfo:
        """Information about this entity/device."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            # If desired, the name for the device could be different to the entity
            "name": self.name,
            "manufacturer": "Netmoon",
        }

    @property
    def is_on(self) -> bool | None:
        return self.on_off

    def update_state(self, data):
        """Light event reporting changes the light state in HA"""
        if "on" in data:
            if data["on"] == 0:
                self.on_off = False
            else:
                self.on_off = True

        if "rgb" in data:
            rgb = data["rgb"]
            blue = rgb & 255
            green = (rgb >> 8) & 255
            red = (rgb >> 16) & 255
            self._attr_rgb_color = (red, green, blue)

        if "level" in data:
            self._attr_brightness = int(data["level"] * 255)

        if "kelvin" in data:
            kelvin = int(data["kelvin"])
            if kelvin > LIGHT_MAX_KELVIN:
                kelvin = LIGHT_MAX_KELVIN
            if kelvin < LIGHT_MIN_KELVIN:
                kelvin = LIGHT_MIN_KELVIN
            kelvin = LIGHT_MAX_KELVIN - (kelvin - LIGHT_MIN_KELVIN)
            self._attr_color_temp = kelvin

    async def async_turn_on(self, **kwargs):
        """Turn on the light, switch color temperature, switch brightness, switch color operations"""
        on = 1
        level = None
        kelvin = None
        rgb = None

        if "color_temp" in kwargs:
            """HA color temperature control page is reversed"""
            kelvin = int(kwargs["color_temp"])
            kelvin = (kelvin - 2700) / (6500 - 2700)
            kelvin = round(LIGHT_MIN_KELVIN + kelvin * (LIGHT_MAX_KELVIN - LIGHT_MIN_KELVIN))
            kelvin = LIGHT_MAX_KELVIN - kelvin + LIGHT_MIN_KELVIN
            if kelvin > LIGHT_MAX_KELVIN:
                kelvin = LIGHT_MAX_KELVIN
            if kelvin < LIGHT_MIN_KELVIN:
                kelvin = LIGHT_MIN_KELVIN
            on = None
            self._attr_color_temp = kwargs["color_temp"]
        if "brightness" in kwargs:
            brightness_normalized = kwargs["brightness"] / 255
            level = round(brightness_normalized, 6)

            on = None
            self._attr_brightness = kwargs["brightness"]

        if "rgb_color" in kwargs:
            rgb = kwargs["rgb_color"]
            rgb = (rgb[0] << 16) + (rgb[1] << 8) + rgb[2]

            on = None
            self._attr_rgb_color = kwargs["rgb_color"]

        await self.exec_command(on=on, level=level, kelvin=kelvin, rgb=rgb)

        self.on_off = True

        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn off the lights"""

        await self.exec_command(on=0)

        self.on_off = False

        self.async_write_ha_state()

    async def exec_command(self, on=None, level=None, kelvin=None, rgb=None):
        message = {
            "seq": 1,
            "data": {}
        }

        if self.is_group:
            message["data"]["room"] = self.room
            message["data"]["subgroup"] = self.subgroup
        else:
            message["data"]["sn"] = self.unique_id

        if on is not None:
            message["data"]["on"] = int(on)

        if level is not None:
            message["data"]["level"] = level

        if kelvin is not None:
            message["data"]["kelvin"] = kelvin

        if rgb is not None:
            message["data"]["rgb"] = rgb

        await self.hass.data[MQTT_CLIENT_INSTANCE].async_publish(
            "P/0/center/q20",
            json.dumps(message),
            0,
            False
        )
