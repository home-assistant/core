"""Support for Firmata switch output."""

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_PIN
from homeassistant.core import HomeAssistant

from .const import CONF_INITIAL_STATE, CONF_NEGATE_STATE, CONF_PIN_MODE, DOMAIN
from .entity import FirmataPinEntity
from .pin import FirmataBinaryDigitalOutput, FirmataPinUsedException

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities
) -> None:
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
                "Could not setup switch on pin %s since pin already in use",
                switch[CONF_PIN],
            )
            continue
        name = switch[CONF_NAME]
        switch_entity = FirmataSwitch(api, config_entry, name, pin)
        new_entities.append(switch_entity)

    if new_entities:
        async_add_entities(new_entities)


class FirmataSwitch(FirmataPinEntity, SwitchEntity):
    """Representation of a switch on a Firmata board."""

    async def async_added_to_hass(self) -> None:
        """Set up a switch."""
        await self._api.start_pin()

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return self._api.is_on

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on switch."""
        await self._api.turn_on()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off switch."""
        await self._api.turn_off()
        self.async_write_ha_state()
