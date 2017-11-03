"""Platform integrating Deconz sensor support.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/sensor/deconz/
"""

import asyncio
import logging

from homeassistant.components.deconz import DATA_DECONZ
from homeassistant.core import callback
from homeassistant.helpers.entity import Entity

DEPENDENCIES = ['deconz']

_LOGGER = logging.getLogger(__name__)


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Setup sensor platform for Deconz."""
    if DATA_DECONZ in hass.data:
        sensors = hass.data[DATA_DECONZ].sensors

    for sensor_id, sensor in sensors.items():
        if sensor.type == 'ZHASwitch':
            async_add_devices([DeconzSensor(sensor_id, sensor)], True)


class DeconzSensor(Entity):
    """Representation of a sensor."""

    def __init__(self, sensor_id, sensor):
        """Setup sensor and add update callback to get data from websocket."""
        self._state = sensor.state
        self.sensor_id = sensor_id
        self.sensor = sensor
        self.sensor.callback = self._update_callback

    @callback
    def _update_callback(self):
        """Update the sensor's state, if needed."""
        self._state = self.sensor.state
        self.async_schedule_update_ha_state()

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def name(self):
        """Return the name of the event."""
        return self.sensor_id

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        return {
            'reachable': self.sensor.reachable,
            'battery': self.sensor.battery,
            'manufacturer': self.sensor.manufacturer,
            'modelid': self.sensor.modelid,
            'swversion': self.sensor.swversion,
            'type': self.sensor.type,
            'uniqueid': self.sensor.uniqueid,
        }
