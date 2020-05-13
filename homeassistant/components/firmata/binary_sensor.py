"""Support for Firmata binary sensor input."""

import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import CONF_NAME
from homeassistant.core import callback

from .board import FirmataBoardPin
from .const import CONF_NEGATE_STATE, DOMAIN, PIN_MODE_INPUT, PIN_MODE_PULLUP

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Firmata binary sensors."""
    new_entities = []

    board_name = config_entry.data[CONF_NAME]
    boards = hass.data[DOMAIN]
    board = boards[board_name]
    for binary_sensor in board.binary_sensors:
        binary_sensor_entity = FirmataDigitalBinaryInput(
            hass, board_name, **binary_sensor
        )
        new_binary_sensor = await binary_sensor_entity.setup_pin()
        if new_binary_sensor:
            new_entities.append(binary_sensor_entity)

    async_add_entities(new_entities)


class FirmataDigitalBinaryInput(FirmataBoardPin, BinarySensorEntity):
    """Representation of a Firmata Digital Input Pin."""

    async def setup_pin(self):
        """Set up a digital input pin."""
        _LOGGER.debug(
            "Setting up binary sensor pin %s for board %s", self._name, self._board_name
        )
        if not self._mark_pin_used():
            _LOGGER.warning(
                "Pin %s already used! Cannot use for binary \
sensor %s",
                str(self._pin),
                self._name,
            )
            return False
        api = self._board.api
        if self._pin_mode == PIN_MODE_INPUT:
            await api.set_pin_mode_digital_input(self._pin, self.latch_callback)
        elif self._pin_mode == PIN_MODE_PULLUP:
            await api.set_pin_mode_digital_input_pullup(self._pin, self.latch_callback)

        # get current state
        new_state = bool((await self._board.api.digital_read(self._firmata_pin))[0])
        if self._conf[CONF_NEGATE_STATE]:
            new_state = not new_state
        self._state = new_state

        return True

    @callback
    async def latch_callback(self, data):
        """Update pin state on callback."""
        if data[1] == self._firmata_pin:
            _LOGGER.debug(
                "Received latch %d for pin %d on board %s",
                data[2],
                self._firmata_pin,
                self._board_name,
            )
            new_state = bool(data[2])
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
