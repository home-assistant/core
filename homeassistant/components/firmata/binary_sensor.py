"""Support for Firmata binary sensor input."""

import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import CONF_NAME

from .pin import FirmataBinaryDigitalInput, FirmataPinUsedException
from .const import CONF_NEGATE_STATE, CONF_PIN, CONF_PIN_MODE, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Firmata binary sensors."""
    new_entities = []

    boards = hass.data[DOMAIN]
    board = boards[config_entry.entry_id]
    for binary_sensor in board.binary_sensors:
        try:
            binary_sensor_entity = FirmataBinarySensor(
                board, config_entry, **binary_sensor
            )
            new_entities.append(binary_sensor_entity)
        except FirmataPinUsedException:
            _LOGGER.error(
                "Could not setup binary sensor on pin %s since pin already in use.",
                binary_sensor[CONF_PIN],
            )
    async_add_entities(new_entities)


class FirmataBinarySensor(BinarySensorEntity):
    """Representation of a binary sensor on a Firmata board."""

    def __init__(self, board, config_entry, **kwargs):
        """Initialize the binary sensor."""
        self._name = kwargs[CONF_NAME]
        self._state = None
        self._config_entry = config_entry
        self._conf = kwargs

        pin = self._conf[CONF_PIN]
        pin_mode = self._conf[CONF_PIN_MODE]
        negate = self._conf[CONF_NEGATE_STATE]

        self._location = (DOMAIN, self._config_entry.entry_id, "pin", pin)
        self._unique_id = "_".join(str(i) for i in self._location)

        self._api = FirmataBinaryDigitalInput(board, pin, pin_mode, negate)

    async def async_added_to_hass(self):
        """Set up a binary sensor."""
        await self._api.start_pin(self.async_write_ha_state)

    async def async_will_remove_from_hass(self):
        """Stop reporting a binary sensor."""
        await self._api.stop_pin()

    @property
    def is_on(self) -> bool:
        """Return true if binary sensor is on."""
        return self._api.is_on

    @property
    def name(self) -> str:
        """Get the name of the pin."""
        return self._name

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    @property
    def unique_id(self):
        """Return a unique identifier for this device."""
        return self._unique_id

    @property
    def device_info(self) -> dict:
        """Return device info."""
        return self._api.board_info
