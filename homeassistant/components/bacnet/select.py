"""Select platform for the BACnet integration."""

from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .bacnet_client import BACnetObjectInfo, BACnetWriteError
from .const import CONF_SELECTED_OBJECTS, DOMAIN, MULTISTATE_OUTPUT_OBJECT_TYPE
from .coordinator import BACnetDeviceCoordinator
from .entity import BACnetEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up BACnet select entities from a config entry."""
    coordinator = entry.runtime_data.coordinator

    if coordinator.data is None:
        return

    selected_objects = entry.options.get(CONF_SELECTED_OBJECTS, [])

    if not selected_objects:
        selected_objects = [
            f"{obj.object_type},{obj.object_instance}"
            for obj in coordinator.data.objects
        ]

    async_add_entities(
        BACnetSelect(coordinator, obj)
        for obj in coordinator.data.objects
        if obj.object_type == MULTISTATE_OUTPUT_OBJECT_TYPE
        and obj.state_text
        and f"{obj.object_type},{obj.object_instance}" in selected_objects
    )


class BACnetSelect(BACnetEntity, SelectEntity):
    """Represent a BACnet multi-state output as a select entity."""

    def __init__(
        self,
        coordinator: BACnetDeviceCoordinator,
        object_info: BACnetObjectInfo,
    ) -> None:
        """Initialize the BACnet select entity."""
        super().__init__(coordinator, object_info)

        self._state_text = object_info.state_text
        if self._state_text:
            self._attr_options = list(self._state_text)

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        value = self._current_value
        if value is None:
            return None

        # Map integer state to text (BACnet multi-state values are 1-indexed)
        if isinstance(value, int) and self._state_text:
            index = value - 1
            if 0 <= index < len(self._state_text):
                return self._state_text[index]

        return str(value)

    async def async_select_option(self, option: str) -> None:
        """Set the selected option."""
        if self._state_text:
            try:
                # Convert text option back to 1-indexed integer
                index = self._state_text.index(option)
            except ValueError as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="invalid_option",
                    translation_placeholders={
                        "option": option,
                        "object": self._obj_key,
                    },
                ) from err
            value: object = index + 1
        else:
            value = option

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
