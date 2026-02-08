"""Sensor platform for the BACnet integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_SELECTED_OBJECTS
from .coordinator import BACnetDeviceCoordinator
from .entity import BACnetEntity
from .units import get_unit_mapping

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

# BACnet object types that produce numeric/analog sensor values
ANALOG_OBJECT_TYPES = {
    "analog-input",
    "analog-output",
    "analog-value",
    "large-analog-value",
    "integer-value",
    "positive-integer-value",
    "accumulator",
    "pulse-converter",
}

# BACnet object types that produce multi-state (enum) sensor values
MULTISTATE_OBJECT_TYPES = {
    "multi-state-input",
    "multi-state-output",
    "multi-state-value",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up BACnet sensors from a config entry."""
    coordinator = entry.runtime_data.coordinator

    if coordinator.data is None:
        return

    # Get selected objects from options (or empty list if not set)
    selected_objects = entry.options.get(CONF_SELECTED_OBJECTS, [])

    # If no selection is configured, add all objects
    if not selected_objects:
        selected_objects = [
            f"{obj.object_type},{obj.object_instance}"
            for obj in coordinator.data.objects
        ]

    entities: list[BACnetSensor | BACnetMultiStateSensor] = []
    for obj in coordinator.data.objects:
        obj_key = f"{obj.object_type},{obj.object_instance}"

        # Only create entities for selected objects
        if obj_key not in selected_objects:
            continue

        if obj.object_type in ANALOG_OBJECT_TYPES:
            entities.append(BACnetSensor(coordinator, obj))
        elif obj.object_type in MULTISTATE_OBJECT_TYPES:
            entities.append(BACnetMultiStateSensor(coordinator, obj))

    async_add_entities(entities)


class BACnetSensor(BACnetEntity, SensorEntity):
    """Represent a BACnet analog/numeric sensor."""

    def __init__(
        self,
        coordinator: BACnetDeviceCoordinator,
        object_info: Any,
    ) -> None:
        """Initialize the BACnet sensor."""
        super().__init__(coordinator, object_info)

        # Map BACnet units to Home Assistant units and device class
        unit_mapping = get_unit_mapping(object_info.units)
        if unit_mapping.ha_unit:
            self._attr_native_unit_of_measurement = unit_mapping.ha_unit
        if unit_mapping.device_class:
            self._attr_device_class = unit_mapping.device_class
        if unit_mapping.state_class:
            self._attr_state_class = unit_mapping.state_class

    @property
    def native_value(self) -> float | int | None:
        """Return the sensor value."""
        value = self._current_value
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                return None
        return None


class BACnetMultiStateSensor(BACnetEntity, SensorEntity):
    """Represent a BACnet multi-state sensor."""

    _attr_state_class: None = None

    def __init__(
        self,
        coordinator: BACnetDeviceCoordinator,
        object_info: Any,
    ) -> None:
        """Initialize the BACnet multi-state sensor."""
        super().__init__(coordinator, object_info)

    @property
    def native_value(self) -> str | int | None:
        """Return the sensor value."""
        value = self._current_value
        if value is None:
            return None
        if isinstance(value, int):
            return value
        return str(value)
