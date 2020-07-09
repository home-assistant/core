"""Support for Firmata switch output."""

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import CONF_NAME

from .pin import FirmataBinaryDigitalOutput, FirmataPinUsedException
from .const import (
    CONF_INITIAL_STATE,
    CONF_NEGATE_STATE,
    CONF_PIN,
    CONF_PIN_MODE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Firmata switches."""
    new_entities = []

    boards = hass.data[DOMAIN]
    board = boards[config_entry.entry_id]
    for switch in board.switches:
        try:
            switch_entity = FirmataSwitch(board, config_entry, **switch)
            new_entities.append(switch_entity)
        except FirmataPinUsedException:
            _LOGGER.error(
                "Could not setup switch on pin %s since pin already in use.",
                switch[CONF_PIN],
            )
    async_add_entities(new_entities)


class FirmataSwitch(SwitchEntity):
    """Representation of a switch on a Firmata board."""

    def __init__(self, board, config_entry, **kwargs):
        """Initialize the switch."""
        self._name = kwargs[CONF_NAME]
        self._config_entry = config_entry
        self._conf = kwargs

        pin = self._conf[CONF_PIN]
        pin_mode = self._conf[CONF_PIN_MODE]
        initial = self._conf[CONF_INITIAL_STATE]
        negate = self._conf[CONF_NEGATE_STATE]

        self._location = (DOMAIN, self._config_entry.entry_id, "pin", pin)
        self._unique_id = "_".join(str(i) for i in self._location)

        self._api = FirmataBinaryDigitalOutput(board, pin, pin_mode, initial, negate)

    async def async_added_to_hass(self):
        """Set up a switch."""
        await self._api.start_pin()
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return self._api.is_on

    async def async_turn_on(self, **kwargs):
        """Turn on switch."""
        _LOGGER.debug("Turning switch %s on", self._name)
        await self._api.turn_on()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn off switch."""
        _LOGGER.debug("Turning switch %s off", self._name)
        await self._api.turn_off()
        self.async_write_ha_state()

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
