"""Platform integrating Deconz binary sensor support.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/binary_sensor/deconz/
"""

import asyncio
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.components.deconz import DECONZ_DATA
from homeassistant.core import callback

DEPENDENCIES = ['deconz']

_LOGGER = logging.getLogger(__name__)


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Setup binary sensor platform for Deconz."""
    from pydeconz.sensor import DECONZ_BINARY_SENSOR
    if DECONZ_DATA in hass.data:
        sensors = hass.data[DECONZ_DATA].sensors

    for _, sensor in sensors.items():
        if sensor.type in DECONZ_BINARY_SENSOR:
            async_add_devices([DeconzBinarySensor(sensor)], True)


class DeconzBinarySensor(BinarySensorDevice):
    """Representation of a binary sensor."""

    def __init__(self, sensor):
        """Setup sensor and add update callback to get data from websocket."""
        self._sensor = sensor
        self._sensor.register_callback(self._update_callback)

    @callback
    def _update_callback(self):
        """Update the sensor's state, if needed."""
        self.async_schedule_update_ha_state()

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._sensor.is_tripped

    @property
    def name(self):
        """Return the name of the event."""
        return self._sensor.name

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        attr = {
            'battery': self._sensor.battery,
            'manufacturer': self._sensor.manufacturer,
            'modelid': self._sensor.modelid,
            'reachable': self._sensor.reachable,
            'swversion': self._sensor.swversion,
            'uniqueid': self._sensor.uniqueid,
        }
        if self._sensor.type == 'ZHAPresence':
            attr['dark'] = self._sensor.dark
        return attr
