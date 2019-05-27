"""Support for Firmata switch output."""

import logging

from homeassistant.components.switch import SwitchDevice
from pymata_aio.constants import Constants as PymataConstants

from .board import FirmataBoardPin
from .const import (CONF_INITIAL_STATE, CONF_NEGATE_STATE, CONF_TYPE,
                    CONF_TYPE_ANALOG, DOMAIN)

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the Firmata switches."""
    _LOGGER.debug("Setting up firmata switches")

    new_entities = []

    boards = hass.data[DOMAIN]
    for board_name in boards:
        board = boards[board_name]
        for switch_name in board.switches:
            switch = board.switches[switch_name]
            switch_entity = FirmataDigitalOut(hass, switch_name, board_name,
                                              **switch)
            await switch_entity.setup_pin()
            new_entities.append(switch_entity)

    async_add_entities(new_entities)


class FirmataDigitalOut(FirmataBoardPin, SwitchDevice):
    """Representation of a Firmata Digital Output Pin."""

    async def setup_pin(self):
        """Set up a digital output pin."""
        _LOGGER.debug("Setting up switch pin %s for board %s", self._name,
                      self._board_name)
        self._conf['pin_mode'] = 'OUTPUT'
        self._conf['firmata_pin_mode'] = PymataConstants.OUTPUT
        self._conf['firmata_pin'] = self._pin
        if self._conf[CONF_TYPE] == CONF_TYPE_ANALOG:
            self._conf['firmata_pin'] += self._board.api.first_analog_pin
        self._attributes.update(self._conf)
        await self._board.api.set_pin_mode(self._conf['firmata_pin'],
                                           self._conf['firmata_pin_mode'])
        if self._conf[CONF_INITIAL_STATE]:
            await self.async_turn_on(update_state=False)
        else:
            await self.async_turn_off(update_state=False)

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return self._state

    async def async_turn_on(self, update_state=True, **kwargs):
        """Turn on switch."""
        _LOGGER.debug("Turning switch %s on", self._name)
        new_pin_state = True and not self._conf[CONF_NEGATE_STATE]
        await self._board.api.digital_pin_write(self._conf['firmata_pin'],
                                                new_pin_state)
        self._state = True
        if update_state:
            self.async_write_ha_state()

    async def async_turn_off(self, update_state=True, **kwargs):
        """Turn off switch."""
        _LOGGER.debug("Turning switch %s off", self._name)
        new_pin_state = False or self._conf[CONF_NEGATE_STATE]
        await self._board.api.digital_pin_write(self._conf['firmata_pin'],
                                                new_pin_state)
        self._state = False
        if update_state:
            self.async_write_ha_state()
