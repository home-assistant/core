"""Comet Blue sensor integration."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import CometBlueDataUpdateCoordinator
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
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Comet Blue Bluetooth sensor based on a config entry."""
    coordinator: CometBlueDataUpdateCoordinator = entry.runtime_data

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

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_native_value = self.coordinator.data.get(self.entity_description.key)

        super()._handle_coordinator_update()
