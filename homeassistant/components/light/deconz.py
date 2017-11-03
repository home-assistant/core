"""Platform integrating Deconz light support.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/light/deconz/
"""

import asyncio
import logging

from homeassistant.components.light import (
    Light, ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS)
from homeassistant.core import callback
from homeassistant.components.deconz import DATA_DECONZ

DEPENDENCIES = ['deconz']

_LOGGER = logging.getLogger(__name__)


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Setup light platform for Deconz."""
    if DATA_DECONZ in hass.data:
        lights = hass.data[DATA_DECONZ].lights

    for light_id, light in lights.items():
        print('setup platform light', light_id, light.__dict__)
        async_add_devices([DeconzLight(light_id, light)], True)


class DeconzLight(Light):
    """Deconz light representation.

    Only supports dimmable lights at the moment.
    """

    def __init__(self, light_id, light):
        """Setup light and add update callback to get data from websocket."""
        self._state = light.state
        self._brightness = light.brightness
        self.light_id = light_id
        self.light = light
        self.light.callback = self._update_callback

    @callback
    def _update_callback(self):
        """Update the sensor's state, if needed."""
        self._state = self.light.state
        self.async_schedule_update_ha_state()

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @property
    def name(self):
        """Return the name of the event."""
        return self.light_id

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @asyncio.coroutine
    def async_turn_on(self, **kwargs):
        """Turn on light."""
        field = '/lights/' + self.light_id + '/state'
        data = {'on': True}
        if ATTR_BRIGHTNESS in kwargs:
            data['bri'] = kwargs[ATTR_BRIGHTNESS]
        yield from self.light.set_state(field, data)

    @asyncio.coroutine
    def async_turn_off(self, **kwargs):
        """Turn off light."""
        field = '/lights/' + self.light_id + '/state'
        data = {'on': False}
        yield from self.light.set_state(field, data)
