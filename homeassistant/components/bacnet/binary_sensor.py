"""Binary sensor platform for the BACnet integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BACnetConfigEntry
from .bacnet_client import BACnetObjectInfo
from .coordinator import BACnetDeviceCoordinator
from .entity import BACnetEntity

PARALLEL_UPDATES = 0

# BACnet object types that produce binary sensor values (read-only)
BINARY_OBJECT_TYPES = {
    "binary-input",
    "binary-value",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BACnetConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up BACnet binary sensors from a config entry."""
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
            """Add new binary sensor entities for newly discovered objects."""
            entities = [
                BACnetBinarySensor(_coord, obj)
                for obj in objects
                if obj.object_type in BINARY_OBJECT_TYPES
                and (not _sel or f"{obj.object_type},{obj.object_instance}" in _sel)
            ]
            if entities:
                async_add_entities(entities)

        _add_new_objects(coordinator.data.objects)
        coordinator.new_objects_callbacks.append(_add_new_objects)


class BACnetBinarySensor(BACnetEntity, BinarySensorEntity):
    """Represent a BACnet binary sensor."""

    def __init__(
        self,
        coordinator: BACnetDeviceCoordinator,
        object_info: Any,
    ) -> None:
        """Initialize the BACnet binary sensor."""
        super().__init__(coordinator, object_info)

    @property
    def is_on(self) -> bool | None:
        """Return the binary sensor state."""
        value = self._current_value
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            # BACnet active (1) = on, inactive (0) = off
            return value == 1
        if isinstance(value, str):
            return value.lower() in ("active", "1", "true", "on")
        return None
