"""Support for Abode Security System lights."""
import logging
from math import ceil

import abodepy.helpers.constants as CONST

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_COLOR_TEMP,
    Light,
)
from homeassistant.util.color import (
    color_temperature_kelvin_to_mired,
    color_temperature_mired_to_kelvin,
)

from . import AbodeDevice
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Abode light devices."""
    data = hass.data[DOMAIN]

    entities = []

    for device in data.abode.get_devices(generic_type=CONST.TYPE_LIGHT):
        entities.append(AbodeLight(data, device))

    async_add_entities(entities)


class AbodeLight(AbodeDevice, Light):
    """Representation of an Abode light."""

    def turn_on(self, **kwargs):
        """Turn on the light."""
        if ATTR_COLOR_TEMP in kwargs and self._device.is_color_capable:
            self._device.set_color_temp(
                int(color_temperature_mired_to_kelvin(kwargs[ATTR_COLOR_TEMP]))
            )

        if ATTR_HS_COLOR in kwargs and self._device.is_color_capable:
            self._device.set_color(kwargs[ATTR_HS_COLOR])

        if ATTR_BRIGHTNESS in kwargs and self._device.is_dimmable:
            # Convert Home Assistant brightness (0-255) to Abode brightness (0-99)
            # If 100 is sent to Abode, response is 99 causing an error
            self._device.set_level(ceil(kwargs[ATTR_BRIGHTNESS] * 99 / 255.0))
        else:
            self._device.switch_on()

    def turn_off(self, **kwargs):
        """Turn off the light."""
        self._device.switch_off()

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._device.is_on

    @property
    def brightness(self):
        """Return the brightness of the light."""
        if self._device.is_dimmable and self._device.has_brightness:
            brightness = int(self._device.brightness)
            # Abode returns 100 during device initialization and device refresh
            if brightness == 100:
                return 255
            # Convert Abode brightness (0-99) to Home Assistant brightness (0-255)
            return ceil(brightness * 255 / 99.0)

    @property
    def color_temp(self):
        """Return the color temp of the light."""
        if self._device.has_color:
            return color_temperature_kelvin_to_mired(self._device.color_temp)

    @property
    def hs_color(self):
        """Return the color of the light."""
        if self._device.has_color:
            return self._device.color

    @property
    def supported_features(self):
        """Flag supported features."""
        if self._device.is_dimmable and self._device.is_color_capable:
            return SUPPORT_BRIGHTNESS | SUPPORT_COLOR | SUPPORT_COLOR_TEMP
        if self._device.is_dimmable:
            return SUPPORT_BRIGHTNESS
        return 0
