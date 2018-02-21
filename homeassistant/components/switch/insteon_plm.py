"""
Support for INSTEON dimmers via PowerLinc Modem.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/switch.insteon_plm/
"""
import asyncio
import logging

from homeassistant.core import callback
from homeassistant.components.switch import (SwitchDevice)
from homeassistant.loader import get_component

DEPENDENCIES = ['insteon_plm']

_LOGGER = logging.getLogger(__name__)


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the INSTEON PLM device class for the hass platform."""
    #entities = []
    plm = hass.data['insteon_plm']

    address = discovery_info['address']
    device = plm.devices[address]
    state_key = discovery_info['state_key']

    state_name = device.states[state_key].name

    _LOGGER.debug('Adding device %s with state name %s to Switch platform.', 
                  device.address.hex, device.states[state_key].name)

    new_entity = None
    if state_name in ['lightOnOff', 'outletTopOnOff', 'outletBottomOnOff']:
        new_entity = InsteonPLMSwitchDevice(device, state_key)
    elif state_name == 'openClosedRelay':
        new_entity = InsteonPLMOpenClosedDevice(device, state_key)

    _LOGGER.debug('Created Switch device with address %s', new_entity.address)

    if new_entity is not None:
        async_add_devices([new_entity])


class InsteonPLMSwitchDevice(SwitchDevice):
    """A Class for an Insteon device."""

    def __init__(self, device, state_key):
        """Initialize the switch."""
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
    def is_on(self):
        """Return the boolean response if the node is on."""
        onlevel = self._insteon_device_state.value
        return bool(onlevel)

    #@property
    #def device_state_attributes(self):
    #    """Provide attributes for display on device card."""
    #    insteon_plm = get_component('insteon_plm')
    #    return insteon_plm.common_attributes(self)

    @callback
    def async_switch_update(self, deviceid, statename, val):
        """Receive notification from transport that new data exists."""
        self.async_schedule_update_ha_state()

    @asyncio.coroutine
    def async_turn_on(self, **kwargs):
        """Turn device on."""
        self._insteon_device_state.on()

    @asyncio.coroutine
    def async_turn_off(self, **kwargs):
        """Turn device off."""
        self._insteon_device_state.off()

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Register INSTEON update events."""
        _LOGGER.debug('Device %s added. Now registering callback.',
                      self.address)
        self.hass.async_add_job(
            self._insteon_device_state.register_updates,
            self.async_switch_update)


class InsteonPLMOpenClosedDevice(SwitchDevice):
    """A Class for an Insteon device."""

    def __init__(self, device, state_key):
        """Initialize the switch."""
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

    #@property
    #def device_state_attributes(self):
    #    """Provide attributes for display on device card."""
    #    insteon_plm = get_component('insteon_plm')
    #    return insteon_plm.common_attributes(self._insteon_device,
    #                                         self._insteon_device_state)

    @callback
    def async_relay_update(self, deviceid, statename, val):
        """Receive notification from transport that new data exists."""
        self.async_schedule_update_ha_state()

    @asyncio.coroutine
    def async_turn_on(self, **kwargs):
        """Turn device on."""
        self._insteon_device_state.open()

    @asyncio.coroutine
    def async_turn_off(self, **kwargs):
        """Turn device off."""
        self._insteon_device_state.close()

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Register INSTEON update events."""
        _LOGGER.debug('Device %s added. Now registering callback.',
                      self.address)
        self.hass.async_add_job(
            self._insteon_device_state.register_updates,
            self.async_relay_update)
