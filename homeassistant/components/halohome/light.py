"""HALO Home integration light platform."""
import logging

import halohome

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    COLOR_MODE_COLOR_TEMP,
    LightEntity,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the HALO Home light platform from a config entry."""
    config = config_entry.data
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
    """HALO Home Light Entity."""

    _attr_max_mireds = 1000000 // 2700
    _attr_min_mireds = 1000000 // 5000
    _attr_supported_color_modes = {COLOR_MODE_COLOR_TEMP}
    _attr_color_mode = COLOR_MODE_COLOR_TEMP

    def __init__(self, device: halohome.Device):
        """Create a new HaloLight object."""
        self._device = device
        self._attr_is_on = False
        self._attr_brightness = 255
        self._attr_color_temp = 200

        self._attr_name = device.device_name
        self._attr_unique_id = device.pid

    async def async_turn_on(self, **kwargs):
        """Change brightness or color of a HALO Home light."""
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
        """Turn off a HALO Home light."""
        await self._device.set_brightness(0)
        self._brightness = 0
        self._attr_is_on = False
