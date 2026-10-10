"""Sensor platform for Axle Energy."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import override

from aioaxlevpp import GridEvent

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import AxleConfigEntry, AxleCoordinator
from .entity import AxleEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class AxleSensorDescription(SensorEntityDescription):
    """Describe one field in a grid event."""

    value_fn: Callable[[GridEvent], str | datetime]


SENSORS = (
    AxleSensorDescription(
        key="import_export",
        translation_key="import_export",
        device_class=SensorDeviceClass.ENUM,
        options=["import", "export"],
        value_fn=lambda event: event.direction,
    ),
    AxleSensorDescription(
        key="start",
        translation_key="start",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda event: event.start,
    ),
    AxleSensorDescription(
        key="end",
        translation_key="end",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda event: event.end,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AxleConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up event metadata sensors."""
    async_add_entities(
        AxleSensor(entry.runtime_data, description) for description in SENSORS
    )


class AxleSensor(AxleEntity, SensorEntity):
    """Represent a field in the current grid event."""

    entity_description: AxleSensorDescription

    def __init__(
        self, coordinator: AxleCoordinator, description: AxleSensorDescription
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"

    @property
    @override
    def native_value(self) -> str | datetime | None:
        """Return unknown when a healthy feed has no participating event."""
        if (event := self.coordinator.data) is None:
            return None
        return self.entity_description.value_fn(event)
