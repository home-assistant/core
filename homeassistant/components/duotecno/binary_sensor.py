"""Support for Duotecno binary sensors."""

from __future__ import annotations

from duotecno.controller import PyDuotecno
from duotecno.unit import ControlUnit, VirtualUnit

from homeassistant.components.binary_sensor import BinarySensorEntity
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
    """Set up Duotecno binary sensor on config_entry."""
    cntrl: PyDuotecno = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        DuotecnoBinarySensor(channel)
        for channel in cntrl.get_units(["ControlUnit", "VirtualUnit"])
    )


class DuotecnoBinarySensor(DuotecnoEntity, BinarySensorEntity):
    """Representation of a DuotecnoBinarySensor."""

    _unit: ControlUnit | VirtualUnit

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self._unit.is_on()
