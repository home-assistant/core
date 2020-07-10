"""Support for Firmata switch output."""

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import CONF_NAME

from .const import (
    CONF_INITIAL_STATE,
    CONF_NEGATE_STATE,
    CONF_PIN,
    CONF_PIN_MODE,
    DOMAIN,
)
from .entity import FirmataEntity
from .pin import FirmataBinaryDigitalOutput, FirmataPinUsedException

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Firmata switches."""
    new_entities = []

    board = hass.data[DOMAIN][config_entry.entry_id]
    for switch in board.switches:
        pin = switch[CONF_PIN]
        pin_mode = switch[CONF_PIN_MODE]
        initial = switch[CONF_INITIAL_STATE]
        negate = switch[CONF_NEGATE_STATE]
        api = FirmataBinaryDigitalOutput(board, pin, pin_mode, initial, negate)
        try:
            api.setup()
        except FirmataPinUsedException:
            _LOGGER.error(
                "Could not setup switch on pin %s since pin already in use.",
                switch[CONF_PIN],
            )
        switch_entity = FirmataSwitch(api, config_entry, **switch)
        new_entities.append(switch_entity)
    async_add_entities(new_entities)


class FirmataSwitch(FirmataEntity, SwitchEntity):
    """Representation of a switch on a Firmata board."""

    def __init__(self, api, config_entry, **kwargs):
        """Initialize the switch."""
        super().__init__(api)
        self._name = kwargs[CONF_NAME]

        location = (config_entry.entry_id, "pin", kwargs[CONF_PIN])
        self._unique_id = "_".join(str(i) for i in location)

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
