"""Support for LightwaveRF lights."""
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    SUPPORT_BRIGHTNESS,
    LightEntity,
)
from homeassistant.const import CONF_NAME

from . import LIGHTWAVE_LINK

MAX_BRIGHTNESS = 255


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Find and return LightWave lights."""
    if not discovery_info:
        return

    lights = []
    lwlink = hass.data[LIGHTWAVE_LINK]

    for device_id, device_config in discovery_info.items():
        name = device_config[CONF_NAME]
        lights.append(LWRFLight(name, device_id, lwlink))

    async_add_entities(lights)


class LWRFLight(LightEntity):
    """Representation of a LightWaveRF light."""

    _attr_supported_features = SUPPORT_BRIGHTNESS
    _attr_should_poll = False

    def __init__(self, name, device_id, lwlink):
        """Initialize LWRFLight entity."""
        self._attr_name = name
        self._device_id = device_id
        self._attr_brightness = MAX_BRIGHTNESS
        self._lwlink = lwlink

    async def async_turn_on(self, **kwargs):
        """Turn the LightWave light on."""
        self._attr_is_on = True

        if ATTR_BRIGHTNESS in kwargs:
            self._attr_brightness = kwargs[ATTR_BRIGHTNESS]

        if self._attr_brightness != MAX_BRIGHTNESS:
            self._lwlink.turn_on_with_brightness(
                self._device_id, self._attr_name, self._attr_brightness
            )
        else:
            self._lwlink.turn_on_light(self._device_id, self._attr_name)

        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the LightWave light off."""
        self._attr_is_on = False
        self._lwlink.turn_off(self._device_id, self._attr_name)
        self.async_write_ha_state()
