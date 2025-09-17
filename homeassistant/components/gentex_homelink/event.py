"""Platform for Event integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo

# Import the device class from the component that you want to support
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, EVENT_PRESSED

# Import keeps mypy happy but is a circular reference otherwise
from .coordinator import HomeLinkCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the entities for the binary sensor."""
    coordinator = config_entry.runtime_data.coordinator
    for device in coordinator.device_data:
        buttons = [
            HomeLinkEventEntity(b.id, b.name, device.id, device.name, coordinator)
            for b in device.buttons
        ]
        coordinator.buttons.extend(buttons)

    async_add_entities(coordinator.buttons)


class HomeLinkEventEntity(CoordinatorEntity[HomeLinkCoordinator], EventEntity):
    """Event Entity."""

    _attr_has_entity_name = True
    _attr_event_types = [EVENT_PRESSED]
    _attr_device_class = EventDeviceClass.BUTTON

    def __init__(
        self,
        id: str,
        param_name: str,
        device_id: str,
        device_name: str,
        coordinator: HomeLinkCoordinator,
    ) -> None:
        """Initialize the event entity."""
        super().__init__(coordinator, context=id)

        self.id: str = id
        self._attr_name: str = param_name
        self._attr_unique_id: str = id
        self._attr_device_info = DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, device_id)
            },
            name=device_name,
        )

        self.name: str = param_name
        self.unique_id: str = id
        self.last_request_id: str | None = None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update this button."""
        if self.id not in self.coordinator.data:
            # Not for us
            return

        data: Mapping[str, Any] = self.coordinator.data
        latest_update = data[self.id]
        # Set button to pressed and then schedule the turnoff
        if latest_update["requestId"] != self.last_request_id:
            self._trigger_event(EVENT_PRESSED)
            self.last_request_id = latest_update["requestId"]

        self.async_write_ha_state()
