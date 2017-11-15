"""Platform integrating Deconz light support.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/light/deconz/
"""

import asyncio
import logging

from homeassistant.components.deconz import (DECONZ_DATA, DOMAIN)
from homeassistant.components.light import (
    Light, ATTR_BRIGHTNESS, ATTR_FLASH, ATTR_COLOR_TEMP, ATTR_EFFECT,
    ATTR_RGB_COLOR, ATTR_TRANSITION, EFFECT_COLORLOOP, FLASH_LONG, FLASH_SHORT,
    SUPPORT_BRIGHTNESS, SUPPORT_COLOR_TEMP, SUPPORT_EFFECT, SUPPORT_FLASH,
    SUPPORT_RGB_COLOR, SUPPORT_TRANSITION, SUPPORT_XY_COLOR)
from homeassistant.core import callback
from homeassistant.util.color import color_RGB_to_xy


DEPENDENCIES = [DOMAIN]

_LOGGER = logging.getLogger(__name__)


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Setup light platform for Deconz."""
    if DECONZ_DATA in hass.data:
        lights = hass.data[DECONZ_DATA].lights
        groups = hass.data[DECONZ_DATA].groups

    for _, light in lights.items():
        async_add_devices([DeconzLight(light)], True)

    for _, group in groups.items():
        if group.lights:
            async_add_devices([DeconzLight(group)], True)


class DeconzLight(Light):
    """Deconz light representation.

    Only supports dimmable lights at the moment.
    """

    def __init__(self, light):
        """Setup light and add update callback to get data from websocket."""
        self._light = light
        self._light.register_callback(self._update_callback)

        self._features = SUPPORT_BRIGHTNESS
        self._features |= SUPPORT_FLASH
        self._features |= SUPPORT_TRANSITION
        if self._light.ct:
            self._features |= SUPPORT_COLOR_TEMP
        if self._light.xy:
            self._features |= SUPPORT_XY_COLOR
            self._features |= SUPPORT_RGB_COLOR
        if self._light.effect:
            self._features |= SUPPORT_EFFECT

    @callback
    def _update_callback(self):
        """Update the sensor's state, if needed."""
        self.async_schedule_update_ha_state()

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._light.brightness

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
        """Return true if device is on."""
        return self._light.state

    @property
    def name(self):
        """Return the name of the event."""
        return self._light.name

    @property
    def supported_features(self):
        """Flag supported features."""
        return self._features

    @property
    def available(self):
        """Return True if entity is available."""
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

        yield from self._light.set_state(data)

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

        yield from self._light.set_state(data)

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        if self._light.type != 'LightGroup':
            attr = {
                'manufacturer': self._light.manufacturer,
                'modelid': self._light.modelid,
                'reachable': self._light.reachable,
                'swversion': self._light.swversion,
                'uniqueid': self._light.uniqueid,
            }
            return attr
