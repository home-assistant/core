"""Support for Duotecno switches."""
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import DuotecnoEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Velbus switch based on config_entry."""
    cntrl = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for channel in cntrl.get_units("SwitchUnit"):
        entities.append(DuotecnoSwitch(channel))
    async_add_entities(entities)


class DuotecnoSwitch(DuotecnoEntity, SwitchEntity):
    """Representation of a switch."""

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        return self._unit.is_on()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the switch to turn on."""
        await self._unit.turn_on()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the switch to turn off."""
        await self._unit.turn_off()
