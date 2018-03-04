"""
Support for deCONZ light.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/light.deconz/
"""
import asyncio

from homeassistant.components.deconz import (
    DOMAIN as DATA_DECONZ, DATA_DECONZ_ID)
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_COLOR_TEMP, ATTR_EFFECT, ATTR_FLASH, ATTR_RGB_COLOR,
    ATTR_TRANSITION, ATTR_XY_COLOR, EFFECT_COLORLOOP, FLASH_LONG, FLASH_SHORT,
    SUPPORT_BRIGHTNESS, SUPPORT_COLOR_TEMP, SUPPORT_EFFECT, SUPPORT_FLASH,
    SUPPORT_RGB_COLOR, SUPPORT_TRANSITION, SUPPORT_XY_COLOR, Light)
from homeassistant.core import callback
from homeassistant.util.color import color_RGB_to_xy

DEPENDENCIES = ['deconz']


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the deCONZ light."""
    if discovery_info is None:
        return

    lights = hass.data[DATA_DECONZ].lights
    groups = hass.data[DATA_DECONZ].groups
    entities = []

    for light in lights.values():
        entities.append(DeconzLight(light))

    for group in groups.values():
        if group.lights:  # Don't create entity for group not containing light
            entities.append(DeconzLight(group))
    async_add_devices(entities, True)


class DeconzLight(Light):
    """Representation of a deCONZ light."""

    def __init__(self, light):
        """Set up light and add update callback to get data from websocket."""
        self._light = light

        self._features = SUPPORT_BRIGHTNESS
        self._features |= SUPPORT_FLASH
        self._features |= SUPPORT_TRANSITION

        if self._light.ct is not None:
            self._features |= SUPPORT_COLOR_TEMP

        if self._light.xy is not None:
            self._features |= SUPPORT_RGB_COLOR
            self._features |= SUPPORT_XY_COLOR

        if self._light.effect is not None:
            self._features |= SUPPORT_EFFECT

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Subscribe to lights events."""
        self._light.register_async_callback(self.async_update_callback)
        self.hass.data[DATA_DECONZ_ID][self.entity_id] = self._light.deconz_id

    @callback
    def async_update_callback(self, reason):
        """Update the light's state."""
        self.async_schedule_update_ha_state()

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._light.brightness

    @property
    def effect_list(self):
        """Return the list of supported effects."""
        return [EFFECT_COLORLOOP]

    @property
    def color_temp(self):
        """Return the CT color value."""
        return self._light.ct

    @property
    def xy_color(self):
        """Return the XY color value."""
        return self._light.xy

    @property
    def is_on(self):
        """Return true if light is on."""
        return self._light.state

    @property
    def name(self):
        """Return the name of the light."""
        return self._light.name

    @property
    def unique_id(self):
        """Return a unique identifier for this light."""
        return self._light.uniqueid

    @property
    def supported_features(self):
        """Flag supported features."""
        return self._features

    @property
    def available(self):
        """Return True if light is available."""
        return self._light.reachable

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @asyncio.coroutine
    def async_turn_on(self, **kwargs):
        """Turn on light."""
        data = {'on': True}

        if ATTR_COLOR_TEMP in kwargs:
            data['ct'] = kwargs[ATTR_COLOR_TEMP]

        if ATTR_RGB_COLOR in kwargs:
            xyb = color_RGB_to_xy(
                *(int(val) for val in kwargs[ATTR_RGB_COLOR]))
            data['xy'] = xyb[0], xyb[1]
            data['bri'] = xyb[2]

        if ATTR_XY_COLOR in kwargs:
            data['xy'] = kwargs[ATTR_XY_COLOR]

        if ATTR_BRIGHTNESS in kwargs:
            data['bri'] = kwargs[ATTR_BRIGHTNESS]

        if ATTR_TRANSITION in kwargs:
            data['transitiontime'] = int(kwargs[ATTR_TRANSITION]) * 10

        if ATTR_FLASH in kwargs:
            if kwargs[ATTR_FLASH] == FLASH_SHORT:
                data['alert'] = 'select'
                del data['on']
            elif kwargs[ATTR_FLASH] == FLASH_LONG:
                data['alert'] = 'lselect'
                del data['on']

        if ATTR_EFFECT in kwargs:
            if kwargs[ATTR_EFFECT] == EFFECT_COLORLOOP:
                data['effect'] = 'colorloop'
            else:
                data['effect'] = 'none'

        yield from self._light.async_set_state(data)

    @asyncio.coroutine
    def async_turn_off(self, **kwargs):
        """Turn off light."""
        data = {'on': False}

        if ATTR_TRANSITION in kwargs:
            data = {'bri': 0}
            data['transitiontime'] = int(kwargs[ATTR_TRANSITION]) * 10

        if ATTR_FLASH in kwargs:
            if kwargs[ATTR_FLASH] == FLASH_SHORT:
                data['alert'] = 'select'
                del data['on']
            elif kwargs[ATTR_FLASH] == FLASH_LONG:
                data['alert'] = 'lselect'
                del data['on']

        yield from self._light.async_set_state(data)
