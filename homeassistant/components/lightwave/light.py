"""Support for LightwaveRF lights."""
from __future__ import annotations

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import LIGHTWAVE_LINK

MAX_BRIGHTNESS = 255


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
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

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
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
