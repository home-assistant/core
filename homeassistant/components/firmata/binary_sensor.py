"""Support for Firmata binary sensor input."""

import logging

from pymata_aio.constants import Constants as PymataConstants

from homeassistant.core import callback
from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.const import CONF_NAME, ATTR_TRIPPED

from .board import FirmataBoardPin
from .const import (CONF_NEGATE_STATE, PIN_MODE_INPUT, PIN_MODE_PULLUP, DOMAIN)

_LOGGER = logging.getLogger(__name__)

PYMATA_DIRECT = PymataConstants.CB_TYPE_DIRECT


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Firmata binary sensors."""
    new_entities = []

    board_name = config_entry.data[CONF_NAME]
    boards = hass.data[DOMAIN]
    board = boards[board_name]
    for binary_sensor in board.binary_sensors:
        binary_sensor_entity = FirmataDigitalBinaryInput(hass, board_name,
                                                         **binary_sensor)
        new_binary_sensor = await binary_sensor_entity.setup_pin()
        if new_binary_sensor:
            new_entities.append(binary_sensor_entity)

    async_add_entities(new_entities)


class FirmataDigitalBinaryInput(FirmataBoardPin, BinarySensorDevice):
    """Representation of a Firmata Digital Input Pin."""

    async def setup_pin(self):
        """Set up a digital input pin."""
        _LOGGER.debug("Setting up binary sensor pin %s for board %s",
                      self._name, self._board_name)
        if not self._mark_pin_used():
            _LOGGER.warning('Pin %s already used! Cannot use for binary \
sensor %s', str(self._pin), self._name)
            return False
        if self._pin_mode == PIN_MODE_INPUT:
            self._firmata_pin_mode = PymataConstants.INPUT
        elif self._pin_mode == PIN_MODE_PULLUP:
            self._firmata_pin_mode = PymataConstants.PULLUP
        self._set_device_info()

        # get current state
        new_state = bool(
            await self._board.api.digital_read(self._firmata_pin))
        if self._conf[CONF_NEGATE_STATE]:
            new_state = not new_state
        self._state = new_state

        # listen for future state changes
        await self._board.api.set_pin_mode(
            self._firmata_pin,
            self._firmata_pin_mode,
            callback=self.latch_callback,
            callback_type=PYMATA_DIRECT
        )
        return True

    @callback
    def latch_callback(self, data):
        """Update pin state on callback."""
        if data[0] == self._firmata_pin:
            new_state = bool(data[1])
            if self._conf[CONF_NEGATE_STATE]:
                new_state = not new_state
            if self._state != new_state:
                self._state = new_state
                if self.entity_id is not None:
                    self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        """Return true if binary sensor is on."""
        return self._state
