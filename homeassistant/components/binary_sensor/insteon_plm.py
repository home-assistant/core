"""
Support for INSTEON dimmers via PowerLinc Modem.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/insteon_plm/
"""
import logging
import asyncio

from homeassistant.core import callback
from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.loader import get_component

DEPENDENCIES = ['insteon_plm']

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES = {'openClosedSensor': 'opening',
                'motionSensor': 'motion',
                'doorSensor': 'door',
                'leakSensor': 'moisture'}

@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the INSTEON PLM device class for the hass platform."""

    state_list = []
    plm = hass.data['insteon_plm']

    for device_info in discovery_info:
        address = device_info['address']
        device = plm.devices[address]
        state_key = device_info['state_key']

        state_list.append(InsteonPLMBinarySensor(hass,
                                                 device,
                                                 state_key))

    async_add_devices(state_list)


class InsteonPLMBinarySensor(BinarySensorDevice):
    """A Class for an Insteon device state."""

    def __init__(self, hass, device, state_key):
        """Initialize the binarysensor."""
        self._hass = hass
        self._insteon_device_state = device.states[state_key]
        self._insteon_device = device
        self._sensor_type = SENSOR_TYPES.get(self._insteon_device_state.name, 
                                             None)

        self._insteon_device_state.register_updates(
            self.async_binarysensor_update)

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def address(self):
        """Return the address of the node."""
        return self._insteon_device.address.human

    @property
    def name(self):
        """Return the name of the node. (used for Entity_ID)"""
        name = ''
        if self._insteon_device_state.group == 0x01:
            name = self._insteon_device.id
        else:
            name = '{:s}_{:d}'.format(self._insteon_device.id, 
                                      self._insteon_device_state.group)
        return name

    @property
    def device_state_attributes(self):
        """Provide attributes for display on device card."""
        insteon_plm = get_component('insteon_plm')
        return insteon_plm.common_attributes(self._insteon_device, 
                                             self._insteon_device_state)

    @callback
    def async_binarysensor_update(self, deviceid, statename, val):
        """Receive notification from transport that new data exists."""
        self._hass.async_add_job(self.async_update_ha_state())

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return self._sensor_type

    @property
    def is_on(self):
        """Return the boolean response if the node is on."""
        sensorstate = self._insteon_device_state.value
        return bool(sensorstate)
