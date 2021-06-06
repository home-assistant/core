"""Light/LED support for the Skybell HD Doorbell."""
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    LightEntity,
)
from homeassistant.core import HomeAssistant
import homeassistant.util.color as color_util

from . import SkybellDevice
from .const import DATA_COORDINATOR, DATA_DEVICES, DOMAIN


def _to_skybell_level(level):
    """Convert the given Home Assistant light level (0-255) to Skybell (0-100)."""
    return int((level * 100) / 255)


def _to_hass_level(level):
    """Convert the given Skybell (0-100) light level to Home Assistant (0-255)."""
    return int((level * 255) / 100)


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    """Set up Skybell switch."""
    skybell_data = hass.data[DOMAIN][entry.entry_id]

    lights = []
    for light in skybell_data[DATA_DEVICES]:
        for device in skybell_data[DATA_DEVICES]:
            lights.append(
                SkybellLight(
                    skybell_data[DATA_COORDINATOR],
                    device,
                    light,
                    entry.entry_id,
                )
            )

    async_add_entities(lights)


class SkybellLight(SkybellDevice, LightEntity):
    """A light implementation for Skybell devices."""

    def __init__(
        self,
        coordinator,
        device,
        light,
        server_unique_id,
    ):
        """Initialize a light for a Skybell device."""
        super().__init__(coordinator, device, light, server_unique_id)
        self._name = self._device.name

    @property
    def name(self):
        """Return the name of the light."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique id of the light."""
        return f"{self._server_unique_id}/{self._name}"

    def turn_on(self, **kwargs):
        """Turn on the light."""
        if ATTR_HS_COLOR in kwargs:
            rgb = color_util.color_hs_to_RGB(*kwargs[ATTR_HS_COLOR])
            self._device.led_rgb = rgb
        elif ATTR_BRIGHTNESS in kwargs:
            self._device.led_intensity = _to_skybell_level(kwargs[ATTR_BRIGHTNESS])
        else:
            self._device.led_intensity = _to_skybell_level(255)

    def turn_off(self, **kwargs):
        """Turn off the light."""
        self._device.led_intensity = 0

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._device.led_intensity > 0

    @property
    def brightness(self):
        """Return the brightness of the light."""
        return _to_hass_level(self._device.led_intensity)

    @property
    def hs_color(self):
        """Return the color of the light."""
        return color_util.color_RGB_to_hs(*self._device.led_rgb)

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS | SUPPORT_COLOR
