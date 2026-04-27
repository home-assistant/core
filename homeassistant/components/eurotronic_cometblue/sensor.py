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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CometBlueConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the client entities."""

    coordinator = entry.runtime_data
    entities = [CometBlueBatterySensorEntity(coordinator)]

    async_add_entities(entities)


class CometBlueBatterySensorEntity(CometBlueBluetoothEntity, SensorEntity):
    """Representation of a sensor."""

    def __init__(
        self,
        coordinator: CometBlueDataUpdateCoordinator,
    ) -> None:
        """Initialize CometBlueSensorEntity."""

        super().__init__(coordinator)
        self.entity_description = SensorEntityDescription(
            key="battery",
            device_class=SensorDeviceClass.BATTERY,
            native_unit_of_measurement=PERCENTAGE,
        )
        self._attr_unique_id = f"{coordinator.address}-{self.entity_description.key}"

    @property
    def native_value(self) -> float | None:
        """Return the entity value to represent the entity state."""
        return self.coordinator.data.battery
