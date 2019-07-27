"""Support for Firmata switch output."""

import logging

from pymata_aio.constants import Constants as PymataConstants

from homeassistant.components.switch import SwitchDevice
from homeassistant.const import CONF_NAME

from .board import FirmataBoardPin
from .const import (CONF_INITIAL_STATE, CONF_NEGATE_STATE,
                    CONF_PIN_MODE_OUTPUT, DOMAIN)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up the Firmata switches."""
    _LOGGER.debug("Setting up firmata switches")

    new_entities = []

    board_name = config_entry.data[CONF_NAME]
    boards = hass.data[DOMAIN]
    board = boards[board_name]
    for switch in board.switches:
        switch_entity = FirmataDigitalOut(hass, board_name, **switch)
        new_switch = await switch_entity.setup_pin()
        if new_switch:
            new_entities.append(switch_entity)
        else:
            _LOGGER.warning('Prevented setting up switch on in use pin %d',
                            switch.pin)

    async_add_devices(new_entities)


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
        if self._pin_mode == CONF_PIN_MODE_OUTPUT:
            self._firmata_pin_mode = PymataConstants.OUTPUT
        self._set_attributes()
        await self._board.api.set_pin_mode(self._firmata_pin,
                                           self._firmata_pin_mode)
        if self._conf[CONF_INITIAL_STATE]:
            await self.async_turn_on(update_state=False)
        else:
            await self.async_turn_off(update_state=False)
        return True

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return self._state

    async def async_turn_on(self, **kwargs):
        """Turn on switch."""
        _LOGGER.debug("Turning switch %s on", self._name)
        update_state = kwargs.get('update_state', True)
        new_pin_state = True and not self._conf[CONF_NEGATE_STATE]
        await self._board.api.digital_pin_write(self._firmata_pin,
                                                new_pin_state)
        self._state = True
        if update_state:
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn off switch."""
        _LOGGER.debug("Turning switch %s off", self._name)
        update_state = kwargs.get('update_state', True)
        new_pin_state = False or self._conf[CONF_NEGATE_STATE]
        await self._board.api.digital_pin_write(self._firmata_pin,
                                                new_pin_state)
        self._state = False
        if update_state:
            self.async_write_ha_state()
