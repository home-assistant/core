"""Support for Firmata switch output."""

import logging

from pymata_aio.constants import Constants as PymataConstants

from homeassistant.components.switch import SwitchDevice
from homeassistant.const import CONF_NAME

from .board import FirmataBoardPin
from .const import (CONF_INITIAL_STATE, CONF_NEGATE_STATE,
                    PIN_MODE_OUTPUT, DOMAIN)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Firmata switches."""
    new_entities = []

    board_name = config_entry.data[CONF_NAME]
    boards = hass.data[DOMAIN]
    board = boards[board_name]
    for switch in board.switches:
        switch_entity = FirmataDigitalOut(hass, board_name, **switch)
        new_switch = await switch_entity.setup_pin()
        if new_switch:
            new_entities.append(switch_entity)

    async_add_entities(new_entities)


class FirmataDigitalOut(FirmataBoardPin, SwitchDevice):
    """Representation of a Firmata Digital Output Pin."""

    async def setup_pin(self):
        """Set up a digital output pin."""
        _LOGGER.debug("Setting up switch pin %s for board %s", self._name,
                      self._board_name)
        if not self._mark_pin_used():
            _LOGGER.warning('Pin %s already used! Cannot use for switch %s',
                            str(self._pin), self._name)
            return False
        if self._pin_mode == PIN_MODE_OUTPUT:
            self._firmata_pin_mode = PymataConstants.OUTPUT
        self._set_device_info()
        await self._board.api.set_pin_mode(self._firmata_pin,
                                           self._firmata_pin_mode)

        self._state = self._conf[CONF_INITIAL_STATE]
        if self._conf[CONF_INITIAL_STATE]:
            new_pin_state = not self._conf[CONF_NEGATE_STATE]
        else:
            new_pin_state = self._conf[CONF_NEGATE_STATE]
        await self._board.api.digital_pin_write(self._firmata_pin,
                                                new_pin_state)
        return True

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return self._state

    async def async_turn_on(self):
        """Turn on switch."""
        _LOGGER.debug("Turning switch %s on", self._name)
        new_pin_state = not self._conf[CONF_NEGATE_STATE]
        await self._board.api.digital_pin_write(self._firmata_pin,
                                                new_pin_state)
        self._state = True
        self.async_write_ha_state()

    async def async_turn_off(self):
        """Turn off switch."""
        _LOGGER.debug("Turning switch %s off", self._name)
        new_pin_state = self._conf[CONF_NEGATE_STATE]
        await self._board.api.digital_pin_write(self._firmata_pin,
                                                new_pin_state)
        self._state = False
        self.async_write_ha_state()
