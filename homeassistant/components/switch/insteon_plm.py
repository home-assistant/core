"""
Support for INSTEON dimmers via PowerLinc Modem.
"""
import logging
import asyncio

from homeassistant.components.switch import (
    ENTITY_ID_FORMAT, SwitchDevice, PLATFORM_SCHEMA)
from homeassistant.const import (
    ATTR_FRIENDLY_NAME, CONF_VALUE_TEMPLATE, STATE_OFF, STATE_ON,
    ATTR_ENTITY_ID, CONF_SWITCHES)
from homeassistant.loader import get_component
import homeassistant.util as util
from homeassistant.components import insteon_plm

DEPENDENCIES = ['insteon_plm']

_LOGGER = logging.getLogger(__name__)

@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Moo."""
    _LOGGER.info('Provisioning Insteon PLM Switches')

    plm = hass.data['insteon_plm']

    def async_insteonplm_switch_callback(device):
        """New device detected from transport."""
        name = device['address']
        address = device['address_hex']

        _LOGGER.info('New INSTEON PLM switch device: %s (%s)', name, address)
        hass.async_add_job(async_add_devices([InsteonPLMSwitchDevice(hass, plm, address, name)]))

    criteria = dict(capability='switch')
    plm.protocol.add_device_callback(async_insteonplm_switch_callback, criteria)


    new_switchs = []
    yield from async_add_devices(new_switchs)

class InsteonPLMSwitchDevice(SwitchDevice):
    """A Class for an Insteon device."""

    def __init__(self, hass, plm, address, name):
        """Initialize the switch."""
        self._hass = hass
        self._plm = plm.protocol
        self._address = address
        self._name = name

        self._plm.add_update_callback(
            self.async_insteonplm_switch_update_callback,
            dict(address=self._address))

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the the name of the node."""
        return self._name

    @property
    def sensor_class(self):
        return

    @property
    def is_on(self):
        """Return the boolean response if the node is on."""
        onlevel = self._plm.get_device_attr(self._address, 'switchstate')
        _LOGGER.debug('on level for %s is %s', self._address, onlevel)
        if onlevel:
            return (onlevel > 0)
        else:
            return False

    @asyncio.coroutine
    def async_turn_on(self, **kwargs):
        """Moo."""
        self._plm.turn_on(self._address, 1)

    @asyncio.coroutine
    def async_turn_off(self, **kwargs):
        """Moo."""
        self._plm.turn_off(self._address)

    def async_insteonplm_switch_update_callback(self, message):
        """Receive notification from transport that new data exists."""
        _LOGGER.info('Received update calback from PLM for %s', self._address)
        self._hass.async_add_job(self.async_update_ha_state(True))

    @property
    def device_state_attributes(self):
        return insteon_plm.common_attributes(self)
