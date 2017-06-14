"""
Lights on Zigbee Home Automation networks.

For more details on this platform, please refer to the documentation
at https://home-assistant.io/components/light.zha/
"""
import asyncio
import logging

from homeassistant.components import light, zha
from homeassistant.util.color import color_RGB_to_xy

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['zha']


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the Zigbee Home Automation lights."""
    discovery_info = zha.get_discovery_info(hass, discovery_info)
    if discovery_info is None:
        return

    endpoint = discovery_info['endpoint']
    try:
        primaries = yield from endpoint.light_color['num_primaries']
        discovery_info['num_primaries'] = primaries
    except (AttributeError, KeyError):
        pass

    async_add_devices([Light(**discovery_info)])


class Light(zha.Entity, light.Light):
    """Representation of a ZHA or ZLL light."""

    _domain = light.DOMAIN

    def __init__(self, **kwargs):
        """Initialize the ZHA light."""
        super().__init__(**kwargs)
        self._supported_features = 0
        self._color_temp = None
        self._xy_color = None
        self._brightness = None

        import bellows.zigbee.zcl.clusters as zcl_clusters
        if zcl_clusters.general.LevelControl.cluster_id in self._clusters:
            self._supported_features |= light.SUPPORT_BRIGHTNESS
            self._brightness = 0
        if zcl_clusters.lighting.Color.cluster_id in self._clusters:
            # Not sure all color lights necessarily support this directly
            # Should we emulate it?
            self._supported_features |= light.SUPPORT_COLOR_TEMP
            # Silly heuristic, not sure if it works widely
            if kwargs.get('num_primaries', 1) >= 3:
                self._supported_features |= light.SUPPORT_XY_COLOR
                self._supported_features |= light.SUPPORT_RGB_COLOR
                self._xy_color = (1.0, 1.0)

    @property
    def is_on(self) -> bool:
        """Return true if entity is on."""
        if self._state == 'unknown':
            return False
        return bool(self._state)

    @asyncio.coroutine
    def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        duration = 5  # tenths of s
        if light.ATTR_COLOR_TEMP in kwargs:
            temperature = kwargs[light.ATTR_COLOR_TEMP]
            yield from self._endpoint.light_color.move_to_color_temp(
                temperature, duration)
            self._color_temp = temperature

        if light.ATTR_XY_COLOR in kwargs:
            self._xy_color = kwargs[light.ATTR_XY_COLOR]
        elif light.ATTR_RGB_COLOR in kwargs:
            xyb = color_RGB_to_xy(
                *(int(val) for val in kwargs[light.ATTR_RGB_COLOR]))
            self._xy_color = (xyb[0], xyb[1])
            self._brightness = xyb[2]
        if light.ATTR_XY_COLOR in kwargs or light.ATTR_RGB_COLOR in kwargs:
            yield from self._endpoint.light_color.move_to_color(
                int(self._xy_color[0] * 65535),
                int(self._xy_color[1] * 65535),
                duration,
            )

        if self._brightness is not None:
            brightness = kwargs.get('brightness', self._brightness or 255)
            self._brightness = brightness
            # Move to level with on/off:
            yield from self._endpoint.level.move_to_level_with_on_off(
                brightness,
                duration
            )
            self._state = 1
            return

        yield from self._endpoint.on_off.on()
        self._state = 1

    @asyncio.coroutine
    def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        yield from self._endpoint.on_off.off()
        self._state = 0

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def xy_color(self):
        """Return the XY color value [float, float]."""
        return self._xy_color

    @property
    def color_temp(self):
        """Return the CT color value in mireds."""
        return self._color_temp

    @property
    def supported_features(self):
        """Flag supported features."""
        return self._supported_features
