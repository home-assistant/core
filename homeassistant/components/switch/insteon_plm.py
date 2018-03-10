"""
Support for INSTEON dimmers via PowerLinc Modem.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/switch.insteon_plm/
"""
import asyncio
import logging

from homeassistant.components.insteon_plm import InsteonPLMEntity
from homeassistant.components.switch import SwitchDevice

DEPENDENCIES = ['insteon_plm']

_LOGGER = logging.getLogger(__name__)


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the INSTEON PLM device class for the hass platform."""
    plm = hass.data['insteon_plm']

    address = discovery_info['address']
    device = plm.devices[address]
    state_key = discovery_info['state_key']

    state_name = device.states[state_key].name

    _LOGGER.debug('Adding device %s entity %s to Switch platform',
                  device.address.hex, device.states[state_key].name)

    new_entity = None
    if state_name in ['lightOnOff', 'outletTopOnOff', 'outletBottomOnOff']:
        new_entity = InsteonPLMSwitchDevice(device, state_key)
    elif state_name == 'openClosedRelay':
        new_entity = InsteonPLMOpenClosedDevice(device, state_key)

    if new_entity is not None:
        async_add_devices([new_entity])


class InsteonPLMSwitchDevice(InsteonPLMEntity, SwitchDevice):
    """A Class for an Insteon device."""

    @property
    def is_on(self):
        """Return the boolean response if the node is on."""
        onlevel = self._insteon_device_state.value
        return bool(onlevel)

    @asyncio.coroutine
    def async_turn_on(self, **kwargs):
        """Turn device on."""
        self._insteon_device_state.on()

    @asyncio.coroutine
    def async_turn_off(self, **kwargs):
        """Turn device off."""
        self._insteon_device_state.off()


class InsteonPLMOpenClosedDevice(InsteonPLMEntity, SwitchDevice):
    """A Class for an Insteon device."""

    @asyncio.coroutine
    def async_turn_on(self, **kwargs):
        """Turn device on."""
        self._insteon_device_state.open()

    @asyncio.coroutine
    def async_turn_off(self, **kwargs):
        """Turn device off."""
        self._insteon_device_state.close()
