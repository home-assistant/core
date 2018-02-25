"""
Support for INSTEON dimmers via PowerLinc Modem.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.insteon_plm/
"""
import asyncio
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.components.insteon_plm import InsteonPLMEntity

DEPENDENCIES = ['insteon_plm']

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES = {'openClosedSensor': 'opening',
                'motionSensor': 'motion',
                'doorSensor': 'door',
                'leakSensor': 'moisture'}


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the INSTEON PLM device class for the hass platform."""
    plm = hass.data['insteon_plm']

    address = discovery_info['address']
    device = plm.devices[address]
    state_key = discovery_info['state_key']

    _LOGGER.debug('Adding device %s entity %s to Binary Sensor platform',
                  device.address.hex, device.states[state_key].name)

    new_entity = InsteonPLMBinarySensor(device, state_key)

    async_add_devices([new_entity])


class InsteonPLMBinarySensor(InsteonPLMEntity, BinarySensorDevice):
    """A Class for an Insteon device entity."""

    def __init__(self, device, state_key):
        """Initialize the INSTEON PLM binary sensor."""
        super().__init__(device, state_key)
        self._sensor_type = SENSOR_TYPES.get(self._insteon_device_state.name)

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return self._sensor_type

    @property
    def is_on(self):
        """Return the boolean response if the node is on."""
        sensorstate = self._insteon_device_state.value
        return bool(sensorstate)
