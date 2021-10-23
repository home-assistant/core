import logging

import halohome
import voluptuous as vol

import homeassistant.helpers.config_validation as cv

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    COLOR_MODE_COLOR_TEMP,
    PLATFORM_SCHEMA,
    LightEntity,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME


_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_HOST, default="https://api.avi-on.com"): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    host = config[CONF_HOST]
    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]

    try:
        connection = await halohome.connect(username, password, host)
    except Exception:
        _LOGGER.error("Could not connect to HALO Home / Avi On Cloud")
        return

    async_add_entities(HaloLight(device) for device in await connection.list_devices())


class HaloLight(LightEntity):
    _attr_max_mireds = 1000000 // 2700
    _attr_min_mireds = 1000000 // 5000
    _attr_supported_color_modes = {COLOR_MODE_COLOR_TEMP}
    _attr_color_mode = COLOR_MODE_COLOR_TEMP

    def __init__(self, device: halohome.Device):
        self._device = device
        self._attr_is_on = False
        self._attr_brightness = 255
        self._attr_color_temp = 200

        self._attr_name = device.device_name
        self._attr_unique_id = device.pid

    async def async_turn_on(self, **kwargs):
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        color_temp = kwargs.get(ATTR_COLOR_TEMP)

        if color_temp is None and brightness is None:
            brightness = 255

        if brightness is not None:
            await self._device.set_brightness(brightness)
            self._brightness = brightness
            self._attr_is_on = True

        if color_temp is not None:
            color_temp = max(self.min_mireds, min(color_temp, self.max_mireds))
            await self._device.set_color_temp(1000000 // color_temp)
            self._color_temp = color_temp
            self._attr_is_on = True

    async def async_turn_off(self, **kwargs):
        await self._device.set_brightness(0)
        self._brightness = 0
        self._attr_is_on = False
