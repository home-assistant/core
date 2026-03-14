"""Sensor platform for the BACnet integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BACnetConfigEntry
from .bacnet_client import BACnetObjectInfo
from .const import ANALOG_OBJECT_TYPES, MULTISTATE_OBJECT_TYPES
from .coordinator import BACnetDeviceCoordinator
from .entity import BACnetEntity
from .units import get_unit_mapping

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BACnetConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up BACnet sensors from a config entry."""
    for coordinator in entry.runtime_data.coordinators.values():
        if coordinator.data is None:
            continue

        selected_objects = coordinator.selected_objects

        @callback
        def _add_new_objects(
            objects: list[BACnetObjectInfo],
            _coord: BACnetDeviceCoordinator = coordinator,
            _sel: list[str] = selected_objects,
        ) -> None:
            """Add new sensor entities for newly discovered objects."""
            entities: list[BACnetSensor | BACnetMultiStateSensor] = []
            for obj in objects:
                if not _sel or f"{obj.object_type},{obj.object_instance}" in _sel:
                    if obj.object_type in ANALOG_OBJECT_TYPES:
                        entities.append(BACnetSensor(_coord, obj))
                    elif obj.object_type in MULTISTATE_OBJECT_TYPES:
                        entities.append(BACnetMultiStateSensor(_coord, obj))
            if entities:
                async_add_entities(entities)

        _add_new_objects(coordinator.data.objects)
        coordinator.new_objects_callbacks.append(_add_new_objects)


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
        # Check for updated state_text from re-discovery
        current_info = self._current_object_info
        if current_info and current_info.state_text != self._state_text:
            self._state_text = current_info.state_text
            if self._state_text:
                self._attr_device_class = SensorDeviceClass.ENUM
                self._attr_options = list(self._state_text)

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
