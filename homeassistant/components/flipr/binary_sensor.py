"""Support for Flipr binary sensors."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_PROBLEM,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import FliprEntity
from .const import DOMAIN

BINARY_SENSORS_TYPES: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="ph_status",
        name="PH Status",
        device_class=DEVICE_CLASS_PROBLEM,
    ),
    BinarySensorEntityDescription(
        key="chlorine_status",
        name="Chlorine Status",
        device_class=DEVICE_CLASS_PROBLEM,
    ),
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Defer sensor setup of flipr binary sensors."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        FliprBinarySensor(
            coordinator,
            description,
        )
        for description in BINARY_SENSORS_TYPES
    )


class FliprBinarySensor(FliprEntity, BinarySensorEntity):
    """Representation of Flipr binary sensors."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize a Flipr sensor."""
        if coordinator.config_entry:
            server_unique_id = coordinator.config_entry.entry_id
        super().__init__(
            coordinator,
            f"{description.key}-{server_unique_id}",
        )
        self.entity_description = description

    @property
    def is_on(self):
        """Return true if the binary sensor is on in case of a Problem is detected."""
        return (
            self.coordinator.data[self.entity_description.key] == "TooLow"
            or self.coordinator.data[self.entity_description.key] == "TooHigh"
        )

    @property
    def name(self):
        """Return the name of the binary sensor."""
        return f"Flipr {self.flipr_id} {self.entity_description.name}"
