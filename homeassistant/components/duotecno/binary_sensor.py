"""Support for Duotecno switches."""

from duotecno.unit import ControlUnit

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
    """Set up Velbus switch based on config_entry."""
    cntrl = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        DuotecnoBinarySensor(channel) for channel in cntrl.get_units("ControlUnit")
    )


class DuotecnoBinarySensor(DuotecnoEntity, BinarySensorEntity):
    """Representation of a BinarySensor."""

    _unit: ControlUnit

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        return self._unit.is_on()
