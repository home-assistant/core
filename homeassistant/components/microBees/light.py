""" Integration microBees """

import logging
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_RGBW_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .servicesMicrobees import sendCommand

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    token = dict(entry.data)["token"]

    bees = dict(entry.data)["bees"]

    lights = []
    for bee in bees:
        if bee.get("active"):
            if (bee.get("productID") == 31
                or bee.get("productID") == 79 ):
                for light in bee.get("actuators"):
                    lights.append(MBLight(light, token))

    async_add_entities(lights)


class MBLight(LightEntity):
    color = [0, 0, 0, 0]

    def __init__(self, act, token):
        self.act = act
        self._state = self.act.get("value")
        self.color = self.act.get("configuration").get("color")
        self.token = token
        self._attr_supported_color_modes = {ColorMode.BRIGHTNESS, ColorMode.RGBW}
        self._attr_min_mireds = 153
        self._attr_max_mireds = 370
        self.async_update()

    @property
    def name(self):
        return self.act.get("name")

    @property
    def unique_id(self):
        return self.act.get("id")

    @property
    def is_on(self):
        return self.act.get("value")

    async def async_turn_on(self, **kwargs):
        _LOGGER.info("turn_on")
        if ATTR_BRIGHTNESS in kwargs:
            self.color[3] = kwargs[ATTR_BRIGHTNESS]
        if ATTR_RGBW_COLOR in kwargs:
            self.color = kwargs[ATTR_RGBW_COLOR]

        data = {
            "actuatorID": self.act.get("id"),
            "command_type": 6,
            "data": {
                "actuatorID": self.act.get("id"),
                "command_type": 6,
                "relay_value": 1,
                "color": self.color,
            },
        }

        await sendCommand(self.token, data)
        self.act["value"] = 1

    async def async_turn_off(self, **kwargs):
        _LOGGER.info("turn_off")
        data = {
            "actuatorID": self.act.get("id"),
            "command_type": 6,
            "data": {
                "actuatorID": self.act.get("id"),
                "command_type": 6,
                "relay_value": 0,
                "color": self.color,
            },
        }

        await sendCommand(self.token, data)
        self.act["value"] = 0

    async def async_update(self):
        self._state = self.act.get("value")
