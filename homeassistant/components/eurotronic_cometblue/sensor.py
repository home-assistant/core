"""Comet Blue sensor integration."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import CometBlueConfigEntry, CometBlueDataUpdateCoordinator
from .entity import CometBlueBluetoothEntity

PARALLEL_UPDATES = 0

DESCRIPTIONS = [
    SensorEntityDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CometBlueConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the client entities."""

    coordinator = entry.runtime_data
    entities: list[CometBlueSensorEntity] = [
        CometBlueSensorEntity(coordinator, description) for description in DESCRIPTIONS
    ]

    async_add_entities(entities)


class CometBlueSensorEntity(CometBlueBluetoothEntity, SensorEntity):
    """Representation of a sensor."""

    def __init__(
        self,
        coordinator: CometBlueDataUpdateCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize CometBlueSensorEntity."""

        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.address}-{description.key}"

    @property
    def native_value(self) -> float | None:
        """Return the entity value to represent the entity state."""
        return getattr(self.coordinator.data, self.entity_description.key, None)
