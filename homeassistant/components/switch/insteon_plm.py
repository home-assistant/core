"""
Support for INSTEON dimmers via PowerLinc Modem.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/insteon_plm/
"""
import logging
import asyncio

from homeassistant.core import callback
from homeassistant.components.switch import (SwitchDevice)
from homeassistant.loader import get_component

DEPENDENCIES = ['insteon_plm']

_LOGGER = logging.getLogger(__name__)


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the INSTEON PLM device class for the hass platform."""

    state_list = []
    plm = hass.data['insteon_plm']

    for device_info in discovery_info:
        address = device_info['address']
        device = plm.devices[address]
        state_key = device_info['state_key']

        state_name = device.states[state_key].name

        if state_name in ['lightOnOff', 'outletTopOnOff', 'outletBottomOnOff']:
            state_list.append(InsteonPLMSwitchDevice(hass,
                                                     device,
                                                     state_key))
        elif state_name == 'openClosedRelay':
            state_list.append(InsteonPLMOpenClosedDevice(hass,
                                                         device,
                                                         state_key))

    async_add_devices(state_list)


class InsteonPLMSwitchDevice(SwitchDevice):
    """A Class for an Insteon device."""

    def __init__(self, hass, device, state_key):
        """Initialize the switch."""
        self._hass = hass
        self._insteon_device_state = device.states[state_key]
        self._insteon_device = device

        self._insteon_device_state.register_updates(self.async_switch_update)

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
    def is_on(self):
        """Return the boolean response if the node is on."""
        onlevel = self._insteon_device_state.value
        return bool(onlevel)

    @property
    def device_state_attributes(self):
        """Provide attributes for display on device card."""
        insteon_plm = get_component('insteon_plm')
        return insteon_plm.common_attributes(self._insteon_device,
                                             self._insteon_device_state)

    @callback
    def async_switch_update(self, deviceid, statename, val):
        """Receive notification from transport that new data exists."""
        self._hass.async_add_job(self.async_update_ha_state())

    @asyncio.coroutine
    def async_turn_on(self, **kwargs):
        """Turn device on."""
        self._insteon_device_state.on()

    @asyncio.coroutine
    def async_turn_off(self, **kwargs):
        """Turn device off"""
        self._insteon_device_state.off()


class InsteonPLMOpenClosedDevice(SwitchDevice):
    """A Class for an Insteon device."""

    def __init__(self, hass, device, state_key):
        """Initialize the switch."""
        self._hass = hass
        self._insteon_device_state = device.states[state_key]
        self._insteon_device = device

        self._insteon_device_state.register_updates(self.async_relay_update)

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
    def is_on(self):
        """Return the boolean response if the node is on."""
        onlevel = self._insteon_device_state.value
        return bool(onlevel)

    @property
    def device_state_attributes(self):
        """Provide attributes for display on device card."""
        insteon_plm = get_component('insteon_plm')
        return insteon_plm.common_attributes(self._insteon_device,
                                             self._insteon_device_state)

    @callback
    def async_relay_update(self, deviceid, statename, val):
        """Receive notification from transport that new data exists."""
        self._hass.async_add_job(self.async_update_ha_state())

    @asyncio.coroutine
    def async_turn_on(self, **kwargs):
        """Turn device on."""
        self._insteon_device_state.open()

    @asyncio.coroutine
    def async_turn_off(self, **kwargs):
        """Turn device off"""
        self._insteon_device_state.close()
