"""Support for Duotecno binary sensors."""

from __future__ import annotations

from duotecno.unit import ControlUnit, VirtualUnit

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DuotecnoConfigEntry
from .entity import DuotecnoEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DuotecnoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Duotecno binary sensor on config_entry."""
    async_add_entities(
        DuotecnoBinarySensor(channel)
        for channel in entry.runtime_data.get_units(["ControlUnit", "VirtualUnit"])
    )


class DuotecnoBinarySensor(DuotecnoEntity, BinarySensorEntity):
    """Representation of a DuotecnoBinarySensor."""

    _unit: ControlUnit | VirtualUnit

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self._unit.is_on()
