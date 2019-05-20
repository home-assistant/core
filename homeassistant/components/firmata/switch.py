"""Support for Firmata output."""
import asyncio

#from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchDevice
from homeassistant.components.switch import SwitchDevice

import voluptuous as vol
import logging
from homeassistant.helpers import (config_validation as cv, device_registry as dr)

from pymata_aio.constants import PymataConstants

from .const import DOMAIN, SWITCH_DEFAULT_NAME, CONF_PINS, CONF_INITIAL_STATE, CONF_NEGATE_STATE
from .board import FirmataBoardPin

DEFAULT_NAME = SWITCH_DEFAULT_NAME
_LOGGER = logging.getLogger(__name__)

#SWITCH_SCHEMA = vol.Schema({
#    vol.Required(CONF_TYPE): cv.string,
#    vol.Required(CONF_PIN): cv.positive_int,
#    vol.Required(CONF_NAME): cv.string
#})

#PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
#    vol.Required(CONF_PINS): vol.Schema([SWITCH_SCHEMA])
#})

# See if this file is running
_LOGGER.fatal('OOOH LOOK A SWITCH!')
print('TESTESTTEST')
async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    _LOGGER.fatal('OOOH LOOK A SWITCH!')
    switches = config.get(CONF_PINS)
    _LOGGER.info(switches.items())


class FirmataDigitalOut(FirmataBoardPin, SwitchDevice):
    """Representation of a Firmata Digital Output Pin."""

    async def setup_pin(self):
        self._mode = PymataConstants.OUTPUT
        #if CONF_DIGITAL_PULLUP is in self._kwargs:
        #    if self._kwargs[CONF_DIGITAL_PULLUP]:
        #        self._mode = PymataConstants.PULLUP
        self.initial = False
        if CONF_INITIAL_STATE in self._kwargs:
            self.initial = self._kwargs[CONF_INITIAL_STATE]
        self.negate = False
        if CONF_NEGATE_STATE in self._kwargs:
            self.negate = self._kwargs[CONF_NEGATE_STATE]
        await self._board.api.set_pin_mode(self._pin, self._mode)
        await self._board.api.digital_pin_write(self._pin, self.intial)
        self._state = self.initial

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._state

    async def async_turn_on(self, **kwargs):
        """Turn on switch."""
        new_pin_state = True and not self.negate
        await self._board.api.digital_pin_write(self._pin, new_pin_state)
        self._state = True

    async def async_turn_off(self, **kwargs):
        """Turn off switch."""
        new_pin_state = False or self.negate
        await self._board.api.digital_pin_write(self._pin, new_pin_state)
        self._state = False
