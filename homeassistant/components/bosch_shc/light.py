"""Platform for light integration."""
from boschshcpy import SHCSession
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_COLOR_TEMP,
    LightEntity,
)
from homeassistant.const import Platform
from homeassistant.util.color import (
    color_hs_to_RGB,
    color_RGB_to_hs,
    color_temperature_mired_to_kelvin,
    color_temperature_to_hs,
)

from .const import DATA_SESSION, DOMAIN
from .entity import SHCEntity


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the light platform."""
    entities = []
    session: SHCSession = hass.data[DOMAIN][config_entry.entry_id][DATA_SESSION]

    for light in session.device_helper.ledvance_lights:
        entities.append(
            LightSwitch(
                device=light,
                parent_id=session.information.unique_id,
                entry_id=config_entry.entry_id,
            )
        )

    if entities:
        async_add_entities(entities)


class LightSwitch(SHCEntity, LightEntity):
    """Representation of a SHC controlled light."""

    @property
    def supported_features(self):
        """Flag supported features."""
        feature = 0
        if self._device.supports_brightness:
            feature |= SUPPORT_BRIGHTNESS
        if self._device.supports_color_temp:
            feature |= SUPPORT_COLOR_TEMP
        if self._device.supports_color_hsb:
            feature |= SUPPORT_COLOR
            feature |= SUPPORT_COLOR_TEMP
        return feature

    @property
    def is_on(self):
        """Return light state."""
        return self._device.state

    @property
    def brightness(self) -> int:
        """Return the brightness of this light between 0..255."""
        brightness_value = (
            round(self._device.brightness * 255 / 100)
            if self._device.brightness
            else None
        )
        return brightness_value

    @property
    def hs_color(self):
        """Return the rgb color of this light."""
        rgb_raw = self._device.rgb
        rgb = ((rgb_raw >> 16) & 0xFF, (rgb_raw >> 8) & 0xFF, rgb_raw & 0xFF)
        return color_RGB_to_hs(*rgb)

    @property
    def color_temp(self):
        """Return the color temp of this light."""
        if self._device.supports_color_temp:
            return self._device.color
        return None

    def turn_on(self, **kwargs):
        """Turn the light on."""
        hs_color = kwargs.get(ATTR_HS_COLOR)
        color_temp = kwargs.get(ATTR_COLOR_TEMP)
        brightness = kwargs.get(ATTR_BRIGHTNESS)

        if brightness is not None and self._device.supports_brightness:
            self._device.brightness = round(brightness * 100 / 255)
        if self._device.supports_color_hsb:
            if color_temp is not None:
                if color_temp < self._device.min_color_temperature:
                    color_temp = self._device.min_color_temperature
                if color_temp > self._device.max_color_temperature:
                    color_temp = self._device.max_color_temperature
                hs_color = color_temperature_to_hs(
                    color_temperature_mired_to_kelvin(color_temp)
                )
            if hs_color is not None:
                rgb = color_hs_to_RGB(*hs_color)
                raw_rgb = (rgb[0] << 16) + (rgb[1] << 8) + rgb[2]
                self._device.rgb = raw_rgb
        if color_temp is not None and self._device.supports_color_temp:
            self._device.color = color_temp

        if not self.is_on:
            self._device.state = True

    def turn_off(self, **kwargs):
        """Turn the light off."""
        self._device.state = False
