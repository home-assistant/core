"""Support for Duotecno switches."""
from typing import Any

from duotecno.unit import SwitchUnit

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import DuotecnoEntity, api_call


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Velbus switch based on config_entry."""
    cntrl = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        DuotecnoSwitch(channel) for channel in cntrl.get_units("SwitchUnit")
    )


class DuotecnoSwitch(DuotecnoEntity, SwitchEntity):
    """Representation of a switch."""

    _unit: SwitchUnit

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        return self._unit.is_on()

    @api_call
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the switch to turn on."""
        await self._unit.turn_on()

    @api_call
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the switch to turn off."""
        await self._unit.turn_off()
