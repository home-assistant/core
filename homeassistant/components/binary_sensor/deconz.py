import asyncio
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.core import callback
from homeassistant.components.deconz import DATA_DECONZ

DEPENDENCIES = ['deconz']

_LOGGER = logging.getLogger(__name__)


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """
    """
    if DATA_DECONZ in hass.data:
        sensors = hass.data[DATA_DECONZ].sensors

    for sensor_id, sensor in sensors.items():
        if sensor.type == 'ZHAPresence':
            async_add_devices([DeconzBinarySensor(sensor_id, sensor)])


class DeconzBinarySensor(BinarySensorDevice):
    """Representation of an device."""

    def __init__(self, sensor_id, sensor):
        self._state = None
        self.sensor_id = sensor_id
        self.sensor = sensor
        self.sensor.callback = self._update_callback

    @callback
    def _update_callback(self):
        """Update the sensor's state, if needed."""
        self._state = self.sensor.is_tripped
        self.async_schedule_update_ha_state()

    @property
    def is_on(self):
        """Return true if device is on."""
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
        return {
            'reachable': self.sensor.reachable,
            'battery': self.sensor.battery,
            'manufacturer': self.sensor.manufacturer,
            'modelid': self.sensor.modelid,
            'swversion': self.sensor.swversion,
            'type': self.sensor.type,
            'uniqueid': self.sensor.uniqueid,
            'dark': self.sensor.dark
        }
