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


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the INSTEON PLM device class for the hass platform."""

    state_list = []
    plm = hass.data['insteon_plm']

    for deviceInfo in discovery_info:
        address = deviceInfo['address']
        device = plm.devices[address]
        stateKey = deviceInfo['stateKey']
        newnames = deviceInfo['newnames']

        _LOGGER.info(
            'Registered device %s state %s with binary_sensor platform %s',
            device.address, device.states[stateKey].name)
        state_list.append(InsteonPLMBinarySensor(hass,
                                                 device,
                                                 stateKey,
                                                 newnames))

    async_add_devices(state_list)


class InsteonPLMBinarySensor(BinarySensorDevice):
    """A Class for an Insteon device state."""

    def __init__(self, hass, device, stateKey, newnames):
        """Initialize the binarysensor."""
        self._hass = hass
        self._state = device.states[stateKey]
        self._device = device
        self._sensor_type = self._stateName_to_sensor_type(self._state.name)
        self._newnames = newnames

        self._state.register_updates(self.async_binarysensor_update)

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def address(self):
        """Return the address of the node."""
        return self._device.address.human

    @property
    def id(self):
        """Return the name of the node."""
        return self._device.id

    @property
    def name(self):
        """Return the name of the node. (used for Entity_ID)"""
        if self._newnames:
            return self._device.id + '_' + self._state.name
        else:
            if self._state.group == 0x01:
                return self._device.id
            else:
                return self._device.id+'_'+str(self._state.group)

    @property
    def device_state_attributes(self):
        """Provide attributes for display on device card."""
        insteon_plm = get_component('insteon_plm')
        return insteon_plm.common_attributes(self._device, self._state)

    @callback
    def async_binarysensor_update(self, deviceid, statename, val):
        """Receive notification from transport that new data exists."""
        _LOGGER.info('Received update calback from PLM for device %s state %s',
                     deviceid, statename)
        self._hass.async_add_job(self.async_update_ha_state())

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return self._sensor_type

    @property
    def is_on(self):
        """Return the boolean response if the node is on."""
        sensorstate = self._state.value
        _LOGGER.info("Sensor for device %s state %s is %s",
                     self.id, self._state.name, sensorstate)
        return bool(sensorstate)

    def _stateName_to_sensor_type(self, stateName):
        if stateName == 'openClosedSensor   ':
            return 'opening'
        elif stateName == 'motionSensor':
            return 'motion'
        elif stateName == 'doorSensor':
            return 'door'
        elif stateName == 'leakSensor':
            return 'moisture'
        else:
            return ""
