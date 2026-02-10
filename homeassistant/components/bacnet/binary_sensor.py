"""Binary sensor platform for the BACnet integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .bacnet_client import BACnetObjectInfo
from .const import CONF_SELECTED_OBJECTS
from .coordinator import BACnetDeviceCoordinator
from .entity import BACnetEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

# BACnet object types that produce binary sensor values (read-only)
BINARY_OBJECT_TYPES = {
    "binary-input",
    "binary-value",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up BACnet binary sensors from a config entry."""
    coordinator = entry.runtime_data.coordinator

    if coordinator.data is None:
        return

    selected_objects = entry.options.get(CONF_SELECTED_OBJECTS, [])

    def _is_selected(obj: BACnetObjectInfo) -> bool:
        """Check if an object is in the selected list."""
        if not selected_objects:
            return True
        return f"{obj.object_type},{obj.object_instance}" in selected_objects

    @callback
    def _add_new_objects(objects: list[BACnetObjectInfo]) -> None:
        """Add new binary sensor entities for newly discovered objects."""
        entities = [
            BACnetBinarySensor(coordinator, obj)
            for obj in objects
            if obj.object_type in BINARY_OBJECT_TYPES and _is_selected(obj)
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
