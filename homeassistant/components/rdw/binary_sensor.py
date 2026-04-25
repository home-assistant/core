"""Support for RDW binary sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from vehicle import Vehicle

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import RDWConfigEntry, RDWDataUpdateCoordinator
from .entity import RDWEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class RDWBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes RDW binary sensor entity."""

    is_on_fn: Callable[[Vehicle], bool | None]


BINARY_SENSORS: tuple[RDWBinarySensorEntityDescription, ...] = (
    RDWBinarySensorEntityDescription(
        key="liability_insured",
        translation_key="liability_insured",
        is_on_fn=lambda vehicle: vehicle.liability_insured,
    ),
    RDWBinarySensorEntityDescription(
        key="pending_recall",
        translation_key="pending_recall",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=lambda vehicle: vehicle.pending_recall,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RDWConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up RDW binary sensors based on a config entry."""
    async_add_entities(
        RDWBinarySensorEntity(entry.runtime_data, description)
        for description in BINARY_SENSORS
        if description.is_on_fn(entry.runtime_data.data) is not None
    )


class RDWBinarySensorEntity(RDWEntity, BinarySensorEntity):
    """Defines an RDW binary sensor."""

    entity_description: RDWBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: RDWDataUpdateCoordinator,
        description: RDWBinarySensorEntityDescription,
    ) -> None:
        """Initialize RDW binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.data.license_plate}_{description.key}"

    @property
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        return bool(self.entity_description.is_on_fn(self.coordinator.data))
