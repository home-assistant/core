"""Dormakaba dKey integration sensor platform."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import DormakabaDkeyConfigEntry, DormakabaDkeyCoordinator
from .entity import DormakabaDkeyEntity

BINARY_SENSOR_DESCRIPTIONS = (
    SensorEntityDescription(
        key="battery_level",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DormakabaDkeyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the lock platform for Dormakaba dKey."""
    coordinator = entry.runtime_data
    async_add_entities(
        DormakabaDkeySensor(coordinator, description)
        for description in BINARY_SENSOR_DESCRIPTIONS
    )


class DormakabaDkeySensor(DormakabaDkeyEntity, SensorEntity):
    """Dormakaba dKey sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DormakabaDkeyCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize a Dormakaba dKey binary sensor."""
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.lock.address}_{description.key}"
        super().__init__(coordinator)

    @callback
    def _async_update_attrs(self) -> None:
        """Handle updating _attr values."""
        self._attr_native_value = getattr(
            self.coordinator.lock, self.entity_description.key
        )
