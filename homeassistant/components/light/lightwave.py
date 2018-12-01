"""
Implements LightwaveRF lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.lightwave/
"""
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS, Light)
from homeassistant.components.lightwave import LIGHTWAVE_LINK
from homeassistant.const import CONF_NAME

DEPENDENCIES = ['lightwave']

MAX_BRIGHTNESS = 255


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Find and return LightWave lights."""
    if not discovery_info:
        return

    lights = []
    lwlink = hass.data[LIGHTWAVE_LINK]

    for device_id, device_config in discovery_info.items():
        name = device_config[CONF_NAME]
        lights.append(LWRFLight(name, device_id, lwlink))

    async_add_entities(lights)


class LWRFLight(Light):
    """Representation of a LightWaveRF light."""

    def __init__(self, name, device_id, lwlink):
        """Initialize LWRFLight entity."""
        self._name = name
        self._device_id = device_id
        self._state = None
        self._brightness = MAX_BRIGHTNESS
        self._lwlink = lwlink

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS

    @property
    def should_poll(self):
        """No polling needed for a LightWave light."""
        return False

    @property
    def name(self):
        """Lightwave light name."""
        return self._name

    @property
    def brightness(self):
        """Brightness of this light between 0..MAX_BRIGHTNESS."""
        return self._brightness

    @property
    def is_on(self):
        """Lightwave light is on state."""
        return self._state

    async def async_turn_on(self, **kwargs):
        """Turn the LightWave light on."""
        self._state = True

        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]

        if self._brightness != MAX_BRIGHTNESS:
            self._lwlink.turn_on_with_brightness(
                self._device_id, self._name, self._brightness)
        else:
            self._lwlink.turn_on_light(self._device_id, self._name)

        self.async_schedule_update_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the LightWave light off."""
        self._state = False
        self._lwlink.turn_off(self._device_id, self._name)
        self.async_schedule_update_ha_state()
