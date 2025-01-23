"""Support for Ecobee Send Message service."""

from __future__ import annotations

from homeassistant.components.notify import NotifyEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import EcobeeData
from .const import DOMAIN
from .entity import EcobeeBaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the ecobee thermostat."""
    data: EcobeeData = hass.data[DOMAIN]
    async_add_entities(
        EcobeeNotifyEntity(data, index) for index in range(len(data.ecobee.thermostats))
    )


class EcobeeNotifyEntity(EcobeeBaseEntity, NotifyEntity):
    """Implement the notification entity for the Ecobee thermostat."""

    _attr_name = None
    _attr_has_entity_name = True

    def __init__(self, data: EcobeeData, thermostat_index: int) -> None:
        """Initialize the thermostat."""
        super().__init__(data, thermostat_index)
        self._attr_unique_id = (
            f"{self.thermostat['identifier']}_notify_{thermostat_index}"
        )

    def send_message(self, message: str, title: str | None = None) -> None:
        """Send a message."""
        self.data.ecobee.send_message(self.thermostat_index, message)
