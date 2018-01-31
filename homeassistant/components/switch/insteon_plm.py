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
    
    for deviceInfo in discovery_info:
        device = deviceInfo['device']
        stateKey = deviceInfo['stateKey']
        subplatform = deviceInfo['subplatform']
        newnames = deviceInfo['newnames']
       
        if subplatform == 'onOff':
            state_list.append(InsteonPLMSwitchDevice( hass, device, state))
        elif subplatform == 'openClosed':
            state_list.append(InsteonPLMOpenClosedDevice( hass, device, state))

    async_add_devices(state_list)


class InsteonPLMSwitchDevice(SwitchDevice):
    """A Class for an Insteon device."""

    def __init__(self, hass, device, state):
        """Initialize the switch."""
        self._hass = hass
        self._state = device.states[stateKey]
        self._device = device 
        if self._state.group == 0x01 and not newnames:
            self._newnames = False
        else:
            self._newnames = True

        self._state.register_updates(self.async_switch_update)

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
    def is_on(self):
        """Return the boolean response if the node is on."""
        onlevel = self._state.value
        _LOGGER.debug('on level for %s is %s', self._device.id, onlevel)
        return bool(onlevel)

    @property
    def device_state_attributes(self):
        """Provide attributes for display on device card."""
        insteon_plm = get_component('insteon_plm')
        return insteon_plm.common_attributes(self._device, self._state)

    @callback
    def async_switch_update(self, deviceid, statename, val):
        """Receive notification from transport that new data exists."""
        _LOGGER.info('Received update calback from PLM for %s', self._device.id)
        self._hass.async_add_job(self.async_update_ha_state())

    @asyncio.coroutine
    def async_turn_on(self, **kwargs):
        """Turn device on."""
        self._state.on()

    @asyncio.coroutine
    def async_turn_off(self, **kwargs):
        """Turn device off"""
        self._state.off()

class InsteonPLMOpenClosedDevice(SwitchDevice):
    """A Class for an Insteon device."""

    def __init__(self, hass, device, stateKey, newnames):
        """Initialize the switch."""
        self._hass = hass
        self._state = device.states[stateKey]
        self._device = device 
        if self._state.group == 0x01 and not newnames:
            self._newnames = False
        else:
            self._newnames = True

        self._state.register_updates(self.async_relay_update)

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
    def is_on(self):
        """Return the boolean response if the node is on."""
        onlevel = self._state.value
        _LOGGER.debug('on level for %s is %s', self._device.id, onlevel)
        return bool(onlevel)

    @property
    def device_state_attributes(self):
        """Provide attributes for display on device card."""
        insteon_plm = get_component('insteon_plm')
        return insteon_plm.common_attributes(self._device, self._state)

    @callback
    def async_relay_update(self, deviceid, statename, val):
        """Receive notification from transport that new data exists."""
        _LOGGER.info('Received update calback from PLM for %s', self._device.id)
        self._hass.async_add_job(self.async_update_ha_state())

    @asyncio.coroutine
    def async_turn_on(self, **kwargs):
        """Turn device on."""
        self._state.open()

    @asyncio.coroutine
    def async_turn_off(self, **kwargs):
        """Turn device off"""
        self._state.close()
