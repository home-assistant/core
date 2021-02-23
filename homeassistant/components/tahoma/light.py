"""Support for TaHoma lights."""
import logging

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    DOMAIN as LIGHT,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    LightEntity,
)
from homeassistant.const import STATE_ON
import homeassistant.util.color as color_util

from .const import COMMAND_OFF, COMMAND_ON, CORE_ON_OFF_STATE, DOMAIN
from .tahoma_entity import TahomaEntity

_LOGGER = logging.getLogger(__name__)

COMMAND_SET_INTENSITY = "setIntensity"
COMMAND_SET_RGB = "setRGB"
COMMAND_WINK = "wink"

CORE_BLUE_COLOR_INTENSITY_STATE = "core:BlueColorIntensityState"
CORE_GREEN_COLOR_INTENSITY_STATE = "core:GreenColorIntensityState"
CORE_LIGHT_INTENSITY_STATE = "core:LightIntensityState"
CORE_RED_COLOR_INTENSITY_STATE = "core:RedColorIntensityState"


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the TaHoma lights from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]

    entities = [
        TahomaLight(device.deviceurl, coordinator)
        for device in data["platforms"][LIGHT]
    ]

    async_add_entities(entities)


class TahomaLight(TahomaEntity, LightEntity):
    """Representation of a TaHoma Light."""

    @property
    def brightness(self) -> int:
        """Return the brightness of this light between 0..255."""
        brightness = self.executor.select_state(CORE_LIGHT_INTENSITY_STATE)
        return round(brightness * 255 / 100)

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self.executor.select_state(CORE_ON_OFF_STATE) == STATE_ON

    @property
    def hs_color(self):
        """Return the hue and saturation color value [float, float]."""
        red = self.executor.select_state(CORE_RED_COLOR_INTENSITY_STATE)
        green = self.executor.select_state(CORE_GREEN_COLOR_INTENSITY_STATE)
        blue = self.executor.select_state(CORE_BLUE_COLOR_INTENSITY_STATE)

        if None in [red, green, blue]:
            return None

        return color_util.color_RGB_to_hs(red, green, blue)

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        supported_features = 0

        if self.executor.has_command(COMMAND_SET_INTENSITY):
            supported_features |= SUPPORT_BRIGHTNESS

        if self.executor.has_command(COMMAND_SET_RGB):
            supported_features |= SUPPORT_COLOR

        return supported_features

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the light on."""
        if ATTR_HS_COLOR in kwargs:
            await self.executor.async_execute_command(
                COMMAND_SET_RGB,
                *[
                    round(float(c))
                    for c in color_util.color_hs_to_RGB(*kwargs[ATTR_HS_COLOR])
                ],
            )

        if ATTR_BRIGHTNESS in kwargs:
            brightness = round(float(kwargs[ATTR_BRIGHTNESS]) / 255 * 100)
            await self.executor.async_execute_command(COMMAND_SET_INTENSITY, brightness)

        else:
            await self.executor.async_execute_command(COMMAND_ON)

    async def async_turn_off(self, **_) -> None:
        """Turn the light off."""
        await self.executor.async_execute_command(COMMAND_OFF)
