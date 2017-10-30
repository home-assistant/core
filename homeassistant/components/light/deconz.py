import asyncio
import logging

from homeassistant.components.light import Light
from homeassistant.core import callback
from homeassistant.components.deconz import DATA_DECONZ

DEPENDENCIES = ['deconz']

_LOGGER = logging.getLogger(__name__)


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """
    """
    if DATA_DECONZ in hass.data:
        lights = hass.data[DATA_DECONZ].lights

    for light_id, light in lights.items():
        print('setup platform light', light_id, light.__dict__)
        async_add_devices([DeconzLight(light_id, light)])


class DeconzLight(Light):
    """
    """
    def __init__(self, light_id, light):
        """
        """
        self._state = None
        self.light_id = light_id
        self.light = light
        self.light.callback = self._update_callback
        print('light initialized')

    @callback
    def _update_callback(self):
        """Update the sensor's state, if needed."""
        self._state = self.light.state
        self.async_schedule_update_ha_state()

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @property
    def name(self):
        """Return the name of the event."""
        return self.light_id

    @property
    def should_poll(self):
        """No polling needed."""
        return False
