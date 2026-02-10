"""Number platform for the BACnet integration."""

from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .bacnet_client import BACnetObjectInfo, BACnetWriteError
from .const import ANALOG_OUTPUT_OBJECT_TYPE, CONF_SELECTED_OBJECTS, DOMAIN
from .coordinator import BACnetDeviceCoordinator
from .entity import BACnetEntity
from .units import get_unit_mapping

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up BACnet number entities from a config entry."""
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
        """Add new number entities for newly discovered objects."""
        entities = [
            BACnetNumber(coordinator, obj)
            for obj in objects
            if obj.object_type == ANALOG_OUTPUT_OBJECT_TYPE and _is_selected(obj)
        ]
        if entities:
            async_add_entities(entities)

    _add_new_objects(coordinator.data.objects)
    coordinator.new_objects_callbacks.append(_add_new_objects)


class BACnetNumber(BACnetEntity, NumberEntity):
    """Represent a BACnet analog output as a number entity."""

    def __init__(
        self,
        coordinator: BACnetDeviceCoordinator,
        object_info: BACnetObjectInfo,
    ) -> None:
        """Initialize the BACnet number entity."""
        super().__init__(coordinator, object_info)

        unit_mapping = get_unit_mapping(object_info.units)
        if unit_mapping.ha_unit:
            self._attr_native_unit_of_measurement = unit_mapping.ha_unit

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        value = self._current_value
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                return None
        return None

    async def async_set_native_value(self, value: float) -> None:
        """Set a new value."""
        try:
            await self.coordinator.client.write_present_value(
                self.coordinator.device_info.address,
                self._object_info.object_type,
                self._object_info.object_instance,
                value,
            )
        except (BACnetWriteError, TimeoutError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="write_error",
                translation_placeholders={
                    "object": self._obj_key,
                    "error": str(err),
                },
            ) from err

        await self.coordinator.async_request_refresh()
