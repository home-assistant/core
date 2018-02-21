"""
Support for INSTEON dimmers via PowerLinc Modem.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/sensor.insteon_plm/
"""
import asyncio
import logging

from homeassistant.core import callback
from homeassistant.helpers.entity import Entity
from homeassistant.loader import get_component

DEPENDENCIES = ['insteon_plm']

_LOGGER = logging.getLogger(__name__)


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the INSTEON PLM device class for the hass platform."""
    _LOGGER.debug("Got here sensor")
    entities = []
    plm = hass.data['insteon_plm']

    address = discovery_info['address']
    device = plm.devices[address]
    state_key = discovery_info['state_key']

    _LOGGER.debug('Adding device %s with state name %s to Sensor platform.', 
                  device.address.hex, device.states[state_key].name)

    entities.append(InsteonPLMSensorDevice(device, state_key))

    async_add_devices(entities)


class InsteonPLMSensorDevice(Entity):
    """A Class for an Insteon device."""

    def __init__(self, device, state_key):
        """Initialize the binarysensor."""
        self._insteon_device_state = device.states[state_key]
        self._insteon_device = device

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def address(self):
        """Return the address of the node."""
        return self._insteon_device.address.human

    def group(self):
        """Return the INSTEON group that the entity responds to."""
        return self._insteon_device_state.group

    @property
    def name(self):
        """Return the name of the node (used for Entity_ID)."""
        name = ''
        if self._insteon_device_state.group == 0x01:
            name = self._insteon_device.id
        else:
            name = '{:s}_{:d}'.format(self._insteon_device.id,
                                      self._insteon_device_state.group)
        return name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._insteon_device_state.value

    @property
    def device_state_attributes(self):
        """Provide attributes for display on device card."""
        insteon_plm = get_component('insteon_plm')
        return insteon_plm.common_attributes(self)

    @callback
    def async_sensor_update(self, deviceid, statename, val):
        """Receive notification from transport that new data exists."""
        self.async_schedule_update_ha_state()

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Register INSTEON update events."""
        self._insteon_device_state.register_updates(self.async_sensor_update)
