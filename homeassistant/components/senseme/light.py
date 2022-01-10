"""Support for Big Ass Fans SenseME light."""
import logging
from typing import Any, Optional

from aiosenseme import SensemeDevice

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR_TEMP,
    LightEntity,
)
from homeassistant.const import CONF_DEVICE

from . import SensemeEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up SenseME lights."""
    device = hass.data[DOMAIN][entry.entry_id][CONF_DEVICE]
    if device.has_light:
        async_add_entities([HASensemeLight(device)])


class HASensemeLight(SensemeEntity, LightEntity):
    """Representation of a Big Ass Fans SenseME light."""

    def __init__(self, device: SensemeDevice) -> None:
        """Initialize the entity."""
        self._device = device
        if device.is_light:
            name = device.name
        else:
            name = f"{device.name} Light"
        super().__init__(device, name)
        self._supported_features = SUPPORT_BRIGHTNESS
        if device.is_light:
            self._supported_features |= SUPPORT_COLOR_TEMP

    @property
    def unique_id(self) -> str:
        """Return a unique identifier for this light."""
        return f"{self._device.uuid}-LIGHT"

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self._device.light_on

    @property
    def brightness(self) -> int:
        """Return the brightness of the light."""
        light_brightness = self._device.light_brightness * 16
        if light_brightness == 256:
            light_brightness = 255
        return int(light_brightness)

    @property
    def color_temp(self) -> Optional[int]:
        """Return the color temp value in mireds."""
        color_temp = int(round(1000000.0 / float(self._device.light_color_temp)))
        return color_temp

    @property
    def min_mireds(self) -> int:
        """Return the coldest color temp that this light supports."""
        color_temp = int(round(1000000.0 / float(self._device.light_color_temp_max)))
        return color_temp

    @property
    def max_mireds(self) -> int:
        """Return the warmest color temp that this light supports."""
        color_temp = int(round(1000000.0 / float(self._device.light_color_temp_min)))
        return color_temp

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return self._supported_features

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        color_temp = kwargs.get(ATTR_COLOR_TEMP)
        if color_temp is not None:
            self._device.light_color_temp = int(round(1000000.0 / float(color_temp)))
        if brightness is None:
            # no brightness, just turn the light on
            self._device.light_on = True
        else:
            # set the brightness, which will also turn on/off light
            if brightness == 255:
                brightness = 256  # this will end up as 16 which is max
            self._device.light_brightness = int(brightness / 16)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        self._device.light_on = False
