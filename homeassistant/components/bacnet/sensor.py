"""Sensor platform for the BACnet integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import ANALOG_OBJECT_TYPES, CONF_SELECTED_OBJECTS, MULTISTATE_OBJECT_TYPES
from .coordinator import BACnetDeviceCoordinator
from .entity import BACnetEntity
from .units import get_unit_mapping

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


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
    """Represent a BACnet multi-state sensor with text enumeration."""

    _attr_state_class: None = None

    def __init__(
        self,
        coordinator: BACnetDeviceCoordinator,
        object_info: Any,
    ) -> None:
        """Initialize the BACnet multi-state sensor."""
        super().__init__(coordinator, object_info)

        # BACnet stateText provides human-readable labels for each state
        # States are 1-indexed: state 1 -> state_text[0], state 2 -> state_text[1]
        self._state_text = object_info.state_text
        if self._state_text:
            self._attr_device_class = SensorDeviceClass.ENUM
            self._attr_options = list(self._state_text)

    @property
    def native_value(self) -> str | None:
        """Return the sensor value as text."""
        value = self._current_value
        if value is None:
            return None

        # Map integer state to text (BACnet multi-state values are 1-indexed)
        if isinstance(value, int) and self._state_text:
            index = value - 1
            if 0 <= index < len(self._state_text):
                return self._state_text[index]

        # Fall back to string representation if no mapping available
        return str(value)
