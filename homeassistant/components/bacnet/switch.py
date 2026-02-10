"""Switch platform for the BACnet integration."""

from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .bacnet_client import BACnetObjectInfo, BACnetWriteError
from .const import BINARY_OUTPUT_OBJECT_TYPE, CONF_SELECTED_OBJECTS, DOMAIN
from .coordinator import BACnetDeviceCoordinator
from .entity import BACnetEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up BACnet switch entities from a config entry."""
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
        """Add new switch entities for newly discovered objects."""
        entities = [
            BACnetSwitch(coordinator, obj)
            for obj in objects
            if obj.object_type == BINARY_OUTPUT_OBJECT_TYPE and _is_selected(obj)
        ]
        if entities:
            async_add_entities(entities)

    _add_new_objects(coordinator.data.objects)
    coordinator.new_objects_callbacks.append(_add_new_objects)


class BACnetSwitch(BACnetEntity, SwitchEntity):
    """Represent a BACnet binary output as a switch entity."""

    def __init__(
        self,
        coordinator: BACnetDeviceCoordinator,
        object_info: BACnetObjectInfo,
    ) -> None:
        """Initialize the BACnet switch entity."""
        super().__init__(coordinator, object_info)

    @property
    def is_on(self) -> bool | None:
        """Return the switch state."""
        value = self._current_value
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return value == 1
        if isinstance(value, str):
            return value.lower() in ("active", "1", "true", "on")
        return None

    async def async_turn_on(self, **kwargs: object) -> None:
        """Turn the switch on."""
        await self._write_value("active")

    async def async_turn_off(self, **kwargs: object) -> None:
        """Turn the switch off."""
        await self._write_value("inactive")

    async def _write_value(self, value: str) -> None:
        """Write a value to the BACnet object."""
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
